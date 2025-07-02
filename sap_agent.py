import os
import json
import logging
import requests
import datetime
import queue
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph

from config.sap_agent_states import (
    State,
    PurchaseHistoryState,
    InventoryState,
    PurchaseRequestState,
    GeneralChatState,
    CreatePurchaseRequestData,
)
from config.sap_agent_prompts import (
    QUESTION_FORMAT_PROMPT,
    AGENT_ROUTING_PROMPT,
    PURCHASE_HISTORY_PROMPT,
    INVENTORY_PROMPT,
    PURCHASE_REQUEST_PROMPT,
    GENERAL_CHAT_PROMPT,
    PURCHASE_REQUEST_CREATION_PROMPT,
    PURCHASE_HISTORY_INTENT_PROMPT,
    INVENTORY_INTENT_PROMPT,
    PURCHASE_REQUEST_CONFIRMATION_PROMPT,
    PURCHASE_REQUEST_INFO_COLLECTION_PROMPT,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SSETokenCallback(BaseCallbackHandler):
    """Callback handler for streaming tokens to a queue"""

    def __init__(self, q: queue.Queue[str]):
        self.q = q

    def on_llm_new_token(self, token: str, **kwargs):
        """Handle new token from LLM"""
        self.q.put(token)

    def on_llm_end(self, *_args, **_kwargs):
        """Handle LLM completion"""
        pass


@dataclass
class SAPAgentConfig:
    """Configuration for SAP Agent"""

    api_base_url: str = "http://localhost:7777"
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 1024
    temperature: float = 0.3
    openai_api_key: str = "your-openai-api-key"
    openai_base_url: str = "https://api.openai.com/v1"


class SAPAPIClient:
    """Client for interacting with SAP API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_purchase_history(
        self,
        category: str = None,
        supplier: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """獲取採購歷史"""
        try:
            params = {}
            if category:
                params["category"] = category
            if supplier:
                params["supplier"] = supplier
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = requests.get(
                f"{self.base_url}/api/purchase-history", params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching purchase history: {e}")
            return {"status": "error", "message": str(e)}

    def get_purchase_detail(self, purchase_id: str) -> Dict[str, Any]:
        """獲取採購詳細資訊"""
        try:
            response = requests.get(
                f"{self.base_url}/api/purchase-history/{purchase_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching purchase detail: {e}")
            return {"status": "error", "message": str(e)}

    def get_inventory(
        self, category: str = None, low_stock: bool = False, location: str = None
    ) -> Dict[str, Any]:
        """獲取庫存資訊"""
        try:
            params = {}
            if category:
                params["category"] = category
            if low_stock:
                params["low_stock"] = "true"
            if location:
                params["location"] = location

            response = requests.get(f"{self.base_url}/api/inventory", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
            return {"status": "error", "message": str(e)}

    def get_product_inventory(self, product_id: str) -> Dict[str, Any]:
        """獲取特定產品庫存"""
        try:
            response = requests.get(f"{self.base_url}/api/inventory/{product_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching product inventory: {e}")
            return {"status": "error", "message": str(e)}

    def create_purchase_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """創建請購單"""
        try:
            response = requests.post(
                f"{self.base_url}/api/purchase-request",
                json=data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating purchase request: {e}")
            return {"status": "error", "message": str(e)}

    def get_purchase_request(self, request_id: str) -> Dict[str, Any]:
        """獲取請購單狀態"""
        try:
            response = requests.get(
                f"{self.base_url}/api/purchase-request/{request_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching purchase request: {e}")
            return {"status": "error", "message": str(e)}

    def get_all_purchase_requests(
        self, requester: str = None, department: str = None, status: str = None
    ) -> Dict[str, Any]:
        """獲取所有請購單"""
        try:
            params = {}
            if requester:
                params["requester"] = requester
            if department:
                params["department"] = department
            if status:
                params["status"] = status

            response = requests.get(
                f"{self.base_url}/api/purchase-requests", params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching all purchase requests: {e}")
            return {"status": "error", "message": str(e)}


class SAPAgent:
    """SAP系統的AI助手"""

    def __init__(self, config: SAPAgentConfig):
        self.config = config
        self.api_client = SAPAPIClient(config.api_base_url)
        self._stream_q: Optional[queue.Queue] = None

        # Initialize LLM
        self.llm = ChatOpenAI(
            model_name=config.model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            streaming=True,
        )

        # Initialize prompts and chains
        self._setup_prompts_and_chains()

    def _setup_prompts_and_chains(self):
        """設置 prompts 和 chains"""
        # Question formatting chain
        self.question_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", QUESTION_FORMAT_PROMPT),
                ("system", "歷史紀錄: {history}"),
                ("human", "問題: {question}"),
            ]
        )
        self.question_chain = self.question_prompt | self.llm | StrOutputParser()

        # Agent routing chain
        self.routing_prompt = ChatPromptTemplate.from_messages(
            [("system", AGENT_ROUTING_PROMPT), ("human", "問題: {question}")]
        )
        self.routing_llm = self.llm.bind_tools(
            tools=[
                PurchaseHistoryState,
                InventoryState,
                PurchaseRequestState,
                GeneralChatState,
            ]
        )
        self.routing_chain = self.routing_prompt | self.routing_llm

        # Response generation chains
        self.purchase_history_prompt = ChatPromptTemplate.from_messages(
            [("system", PURCHASE_HISTORY_PROMPT), ("human", "請回答問題")]
        )
        self.purchase_history_chain = (
            self.purchase_history_prompt | self.llm | StrOutputParser()
        )

        self.inventory_prompt = ChatPromptTemplate.from_messages(
            [("system", INVENTORY_PROMPT), ("human", "請回答問題")]
        )
        self.inventory_chain = self.inventory_prompt | self.llm | StrOutputParser()

        self.purchase_request_prompt = ChatPromptTemplate.from_messages(
            [("system", PURCHASE_REQUEST_PROMPT), ("human", "請回答問題")]
        )
        self.purchase_request_chain = (
            self.purchase_request_prompt | self.llm | StrOutputParser()
        )

        self.general_chat_prompt = ChatPromptTemplate.from_messages(
            [("system", GENERAL_CHAT_PROMPT), ("human", "請回答問題")]
        )
        self.general_chat_chain = (
            self.general_chat_prompt | self.llm | StrOutputParser()
        )

    def attach_stream_queue(self, q: queue.Queue) -> None:
        """Attach a stream queue to the instance"""
        self._stream_q = q

    def _stream_text(self, text: str) -> None:
        """Stream text character by character into queue"""
        if self._stream_q is None:
            return
        for ch in text:
            self._stream_q.put(ch)

    @contextmanager
    def _temp_stream(self):
        """Context manager for temporary streaming"""
        if self._stream_q is None:
            yield
            return

        token_cb = SSETokenCallback(self._stream_q)
        if getattr(self.llm, "callbacks", None) is None:
            self.llm.callbacks = []

        self.llm.callbacks.append(token_cb)
        try:
            yield
        finally:
            try:
                self.llm.callbacks.remove(token_cb)
            except ValueError:
                pass

    def _format_history_to_string(
        self, history_list: Optional[List[Dict[str, str]]]
    ) -> str:
        """Convert history list to readable string format"""
        if not history_list:
            return "無歷史紀錄"

        history_parts = []
        for message in history_list:
            if message.get("role") != "system":
                role = message.get("role", "unknown")
                content = message.get("content", "")
                history_parts.append(f"{role}: {content}")

        return "\n".join(history_parts)

    # Workflow node methods
    def format_question(self, state: Dict[str, Any]) -> Dict[str, str]:
        """格式化使用者問題"""
        logger.info("FORMAT QUESTION")

        question = state["question"]
        history = self._format_history_to_string(state.get("chat_history"))

        try:
            formatted_question = self.question_chain.invoke(
                {"question": question, "history": history}
            )

            logger.info(f"Original: {question}")
            logger.info(f"Formatted: {formatted_question}")

            return {"formatted_question": formatted_question}
        except Exception as e:
            logger.error(f"Error formatting question: {e}")
            return {"formatted_question": question}

    def route_agent(self, state: Dict[str, Any]) -> str:
        """路由到適當的 agent"""
        logger.info("ROUTE AGENT")

        # 首先檢查是否有待處理的請購單狀態
        purchase_state = state.get("purchase_request_state")
        pending_data = state.get("pending_purchase_data")

        # 如果請購單已完成，清除狀態
        if purchase_state == "completed":
            logger.info("Purchase request completed, clearing state")
            purchase_state = None
            pending_data = None

        question = state["formatted_question"]

        # 檢查是否在請購單流程中但想要查詢其他資訊
        if purchase_state in ["collecting_info", "ready_to_create"]:
            # 檢查是否是查詢相關的問題（採購歷史、庫存等）
            query_keywords = ["查詢", "查看", "價格", "歷史", "採購記錄", "庫存", "多少錢", "成本"]
            if any(keyword in question for keyword in query_keywords):
                logger.info("User wants to query information during purchase request flow")
                # 暫時保存請購單狀態，但允許查詢
                return self._route_query_during_purchase_flow(state)
            
            # 否則繼續請購單流程
            if purchase_state == "ready_to_create" and pending_data:
                logger.info("ROUTE TO PURCHASE REQUEST CONFIRMATION")
                return "purchase_request_confirmation"
            elif purchase_state == "collecting_info":
                logger.info("ROUTE TO PURCHASE REQUEST INFO COLLECTION")
                return "purchase_request_info_collection"

        # 正常路由邏輯
        try:
            source = self.routing_chain.invoke({"question": question})

            if len(source.tool_calls) == 0:
                logger.info("ROUTE TO GENERAL CHAT")
                return "general_chat"

            agent_name = source.tool_calls[0]["name"]

            if agent_name == "PurchaseHistoryState":
                logger.info("ROUTE TO PURCHASE HISTORY")
                return "purchase_history"
            elif agent_name == "InventoryState":
                logger.info("ROUTE TO INVENTORY")
                return "inventory"
            elif agent_name == "PurchaseRequestState":
                logger.info("ROUTE TO PURCHASE REQUEST")
                return "purchase_request"
            else:
                logger.info("ROUTE TO GENERAL CHAT")
                return "general_chat"

        except Exception as e:
            logger.error(f"Error in routing: {e}")
            return "general_chat"

    def _route_query_during_purchase_flow(self, state: Dict[str, Any]) -> str:
        """在請購單流程中處理查詢請求的路由"""
        question = state["formatted_question"]
        
        try:
            source = self.routing_chain.invoke({"question": question})
            
            if len(source.tool_calls) > 0:
                agent_name = source.tool_calls[0]["name"]
                
                if agent_name == "PurchaseHistoryState":
                    logger.info("ROUTE TO PURCHASE HISTORY (during purchase flow)")
                    return "purchase_history_during_flow"
                elif agent_name == "InventoryState":
                    logger.info("ROUTE TO INVENTORY (during purchase flow)")
                    return "inventory_during_flow"
            
            # 如果無法識別為查詢，回到請購單流程
            purchase_state = state.get("purchase_request_state")
            if purchase_state == "collecting_info":
                return "purchase_request_info_collection"
            else:
                return "purchase_request_confirmation"
                
        except Exception as e:
            logger.error(f"Error in query routing during purchase flow: {e}")
            # 發生錯誤時回到請購單流程
            purchase_state = state.get("purchase_request_state")
            if purchase_state == "collecting_info":
                return "purchase_request_info_collection"
            else:
                return "purchase_request_confirmation"

    def handle_purchase_request(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理請購單申請"""
        logger.info("HANDLE PURCHASE REQUEST")
        logger.info("Starting purchase request creation process")

        question = state["formatted_question"]
        history = self._format_history_to_string(state.get("chat_history"))
        required_fields = ["product_name", "quantity", "unit_price", "requester", "department"]

        # 使用 LLM 提取資訊
        prompt = ChatPromptTemplate.from_messages([
            ("system", PURCHASE_REQUEST_CREATION_PROMPT),
            ("human", "使用者需求：{question}\n歷史紀錄：{history}")
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            response = chain.invoke({
                "question": question,
                "history": history
            })
            logger.info(f"Info extraction response from LLM: {response}")

            # 嘗試解析 JSON
            try:
                info = json.loads(response)
                logger.info(f"Successfully parsed extracted info: {info}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM response: {response}")
                info = {}

            # 檢查必需欄位
            missing_fields = [field for field in required_fields if not info.get(field)]

            if missing_fields:
                logger.info(f"Missing required fields: {missing_fields}")
                return {
                    "purchase_request_state": "collecting_info",
                    "pending_purchase_data": info,
                    "missing_fields": missing_fields
                }
            else:
                # 所有資訊都收集到了，準備創建請購單
                return {
                    "purchase_request_state": "ready_to_create",
                    "pending_purchase_data": info
                }

        except Exception as e:
            logger.error(f"Error in purchase request handling: {e}")
            return {
                "purchase_request_state": "collecting_info",
                "pending_purchase_data": {},
                "missing_fields": required_fields
            }

    def handle_purchase_request_info_collection(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理請購單資訊收集"""
        logger.info("HANDLE PURCHASE REQUEST INFO COLLECTION")

        question = state["formatted_question"]
        pending_data = state.get("pending_purchase_data", {})

        # 使用 LLM 從新的用戶輸入中提取資訊
        prompt = ChatPromptTemplate.from_messages([
            ("system", PURCHASE_REQUEST_INFO_COLLECTION_PROMPT),
            ("human", f"目前已有資訊：{json.dumps(pending_data, ensure_ascii=False)}\n新的用戶輸入：{question}")
        ])
        chain = prompt | self.llm | StrOutputParser()

        try:
            response = chain.invoke({})
            logger.info(f"Info extraction response: {response}")

            # 嘗試解析 JSON
            try:
                new_info = json.loads(response)
                # 合併新資訊和現有資訊
                merged_info = {**pending_data, **new_info}
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM response: {response}")
                merged_info = pending_data

            # 檢查必需欄位
            required_fields = ["product_name", "quantity", "unit_price", "requester", "department"]
            missing_fields = [field for field in required_fields if not merged_info.get(field)]

            if missing_fields:
                logger.info(f"Still missing fields: {missing_fields}")
                return {
                    "purchase_request_state": "collecting_info",
                    "pending_purchase_data": merged_info,
                    "missing_fields": missing_fields
                }
            else:
                # 所有資訊都收集到了，創建請購单
                logger.info("All required information collected - Creating purchase request")
                result = self._create_purchase_request(merged_info)
                return {
                    "purchase_request_state": "completed",
                    "pending_purchase_data": None,
                    "purchase_request_result": result
                }

        except Exception as e:
            logger.error(f"Error in purchase request info collection: {e}")
            return {
                "purchase_request_state": "collecting_info",
                "pending_purchase_data": pending_data,
                "missing_fields": ["product_name", "quantity", "unit_price", "requester", "department"]
            }

    def handle_purchase_request_confirmation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理請購單確認"""
        logger.info("HANDLE PURCHASE REQUEST CONFIRMATION")

        pending_data = state.get("pending_purchase_data", {})
        
        # 創建請購單
        result = self._create_purchase_request(pending_data)
        
        return {
            "purchase_request_state": "completed",
            "pending_purchase_data": None,
            "purchase_request_result": result
        }

    def _create_purchase_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """創建請購單的內部方法"""
        try:
            # 準備請購單數據
            request_data = {
                "product_name": data.get("product_name"),
                "quantity": data.get("quantity"),
                "unit_price": data.get("unit_price"),
                "requester": data.get("requester"),
                "department": data.get("department"),
                "reason": data.get("reason", "業務需求"),
                "urgent": data.get("urgent", False),
                "expected_delivery_date": data.get("expected_delivery_date", "")
            }

            # 調用 API 創建請購單
            result = self.api_client.create_purchase_request(request_data)
            return result

        except Exception as e:
            logger.error(f"Error creating purchase request: {e}")
            return {"status": "error", "message": str(e)}

    def handle_purchase_history(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理採購歷史查詢"""
        logger.info("HANDLE PURCHASE HISTORY")

        question = state["formatted_question"]

        # 分析使用者意圖
        intent_prompt = ChatPromptTemplate.from_messages([
            ("system", PURCHASE_HISTORY_INTENT_PROMPT),
            ("human", "使用者問題：{question}")
        ])

        # 可用的產品類別
        available_categories = ["筆記型電腦", "智慧型手機", "顯示器", "平板電腦", "3C產品"]

        try:
            intent_chain = intent_prompt | self.llm | StrOutputParser()
            intent_response = intent_chain.invoke({
                "question": question,
                "available_categories": available_categories
            })

            # 解析意圖
            try:
                intent_data = json.loads(intent_response)
            except json.JSONDecodeError:
                intent_data = {"query_type": "all"}

            # 根據意圖調用 API
            api_params = {}
            if intent_data.get("category"):
                api_params["category"] = intent_data["category"]
            if intent_data.get("supplier"):
                api_params["supplier"] = intent_data["supplier"]
            if intent_data.get("start_date"):
                api_params["start_date"] = intent_data["start_date"]
            if intent_data.get("end_date"):
                api_params["end_date"] = intent_data["end_date"]

            # 調用 API
            api_data = self.api_client.get_purchase_history(**api_params)

            return {
                "agent_type": "purchase_history",
                "api_data": api_data
            }

        except Exception as e:
            logger.error(f"Error in purchase history handling: {e}")
            return {
                "agent_type": "purchase_history",
                "api_data": {"status": "error", "message": str(e)}
            }

    def handle_inventory(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理庫存查詢"""
        logger.info("HANDLE INVENTORY")

        question = state["formatted_question"]

        # 分析使用者意圖
        intent_prompt = ChatPromptTemplate.from_messages([
            ("system", INVENTORY_INTENT_PROMPT),
            ("human", "使用者問題：{question}")
        ])

        # 可用的產品類別
        available_categories = ["筆記型電腦", "智慧型手機", "顯示器", "平板電腦", "3C產品"]

        try:
            intent_chain = intent_prompt | self.llm | StrOutputParser()
            intent_response = intent_chain.invoke({
                "question": question,
                "available_categories": available_categories
            })

            # 解析意圖
            try:
                intent_data = json.loads(intent_response)
            except json.JSONDecodeError:
                intent_data = {"query_type": "all"}

            # 根據意圖調用 API
            api_params = {}
            if intent_data.get("category"):
                api_params["category"] = intent_data["category"]
            if intent_data.get("low_stock_filter"):
                api_params["low_stock"] = intent_data["low_stock_filter"]
            if intent_data.get("location"):
                api_params["location"] = intent_data["location"]

            # 調用 API
            api_data = self.api_client.get_inventory(**api_params)

            return {
                "agent_type": "inventory",
                "api_data": api_data
            }

        except Exception as e:
            logger.error(f"Error in inventory handling: {e}")
            return {
                "agent_type": "inventory",
                "api_data": {"status": "error", "message": str(e)}
            }

    def handle_general_chat(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理一般對話"""
        logger.info("HANDLE GENERAL CHAT")

        return {
            "agent_type": "general_chat",
            "api_data": {}
        }

    def generate_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成最終回應"""
        logger.info("GENERATE RESPONSE")

        start_time = time.time()

        agent_type = state.get("agent_type", "general_chat")
        api_data = state.get("api_data", {})
        question = state.get("formatted_question", state.get("question", ""))
        history = self._format_history_to_string(state.get("chat_history"))

        # 檢查是否有請購單相關的狀態需要處理
        purchase_state = state.get("purchase_request_state")
        missing_fields = state.get("missing_fields", [])
        pending_data = state.get("pending_purchase_data", {})
        purchase_result = state.get("purchase_request_result")
        query_during_flow = state.get("query_result_during_flow", False)

        try:
            with self._temp_stream():
                if purchase_state == "collecting_info":
                    # 請購單資訊收集階段
                    response = self._generate_info_collection_response(missing_fields, pending_data)
                
                elif purchase_state == "completed" and purchase_result:
                    # 請購單創建完成
                    response = self._generate_purchase_success_response(purchase_result)
                
                elif query_during_flow and agent_type in ["purchase_history", "inventory"]:
                    # 在請購單流程中進行查詢
                    response = self._generate_query_response_during_flow(agent_type, api_data, question, history, state)
                
                else:
                    # 正常回應生成
                    if agent_type == "purchase_history":
                        response = self.purchase_history_chain.invoke({
                            "api_data": json.dumps(api_data, ensure_ascii=False, indent=2),
                            "history": history,
                            "question": question
                        })
                    elif agent_type == "inventory":
                        response = self.inventory_chain.invoke({
                            "api_data": json.dumps(api_data, ensure_ascii=False, indent=2),
                            "history": history,
                            "question": question
                        })
                    elif agent_type == "purchase_request":
                        response = self.purchase_request_chain.invoke({
                            "api_data": json.dumps(api_data, ensure_ascii=False, indent=2),
                            "history": history,
                            "question": question
                        })
                    else:  # general_chat
                        response = self.general_chat_chain.invoke({
                            "history": history,
                            "question": question
                        })

            # 計算處理時間
            processing_time = time.time() - start_time
            logger.info(f"Total processing time: {processing_time:.2f}s")

            # 如果是查詢結果且在請購單流程中，添加提示回到請購單流程
            if query_during_flow:
                response += "\n\n繼續完成您的請購單申請，請提供剩餘的必要資訊。"

            return {"generation": response}

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {"generation": f"抱歉，生成回應時發生錯誤：{str(e)}"}

    def _generate_info_collection_response(self, missing_fields: List[str], pending_data: Dict[str, Any]) -> str:
        """生成請購單資訊收集回應"""
        field_translations = {
            "product_name": "產品名稱",
            "quantity": "數量",
            "unit_price": "預估單價",
            "requester": "申請人",
            "department": "部門"
        }
        
        missing_chinese = [field_translations.get(field, field) for field in missing_fields]
        
        response = "請提供以下必要資訊以完成請購單申請：\n\n"
        for field in missing_chinese:
            response += f"• {field}\n"
        
        if pending_data:
            response += "\n\n目前已收集到的資訊：\n"
            for key, value in pending_data.items():
                if value:
                    chinese_key = field_translations.get(key, key)
                    response += f"- {chinese_key}：{value}\n"
        
        response += "\n請提供缺少的資訊，例如：\n"
        response += "申請人：張三\n"
        response += "部門：IT部門\n"
        response += "預估單價：50000"
        
        return response

    def _generate_purchase_success_response(self, purchase_result: Dict[str, Any]) -> str:
        """生成請購單創建成功回應"""
        if purchase_result.get("status") == "success":
            request_id = purchase_result.get("request_id", "未知")
            response = f"✅ 請購單創建成功！\n\n"
            response += f"請購單編號：{request_id}\n"
            response += f"狀態：待審核\n\n"
            response += f"您可以使用請購單編號追蹤審核進度。如有任何問題，請聯繫相關部門主管。"
        else:
            response = f"❌ 請購單創建失敗：{purchase_result.get('message', '未知錯誤')}"
        
        return response

    def _generate_query_response_during_flow(self, agent_type: str, api_data: Dict[str, Any], question: str, history: str, state: Dict[str, Any]) -> str:
        """在請購單流程中生成查詢回應"""
        if agent_type == "purchase_history":
            response = self.purchase_history_chain.invoke({
                "api_data": json.dumps(api_data, ensure_ascii=False, indent=2),
                "history": history,
                "question": question
            })
        elif agent_type == "inventory":
            response = self.inventory_chain.invoke({
                "api_data": json.dumps(api_data, ensure_ascii=False, indent=2),
                "history": history,
                "question": question
            })
        else:
            response = "查詢完成。"
        
        return response

    def handle_purchase_history_during_flow(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """在請購單流程中處理採購歷史查詢"""
        logger.info("HANDLE PURCHASE HISTORY DURING FLOW")
        
        # 執行採購歷史查詢
        history_result = self.handle_purchase_history(state)
        
        # 保持請購單狀態
        return {
            **history_result,
            "purchase_request_state": state.get("purchase_request_state"),
            "pending_purchase_data": state.get("pending_purchase_data"),
            "missing_fields": state.get("missing_fields"),
            "query_result_during_flow": True
        }

    def handle_inventory_during_flow(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """在請購單流程中處理庫存查詢"""
        logger.info("HANDLE INVENTORY DURING FLOW")
        
        # 執行庫存查詢
        inventory_result = self.handle_inventory(state)
        
        # 保持請購單狀態
        return {
            **inventory_result,
            "purchase_request_state": state.get("purchase_request_state"),
            "pending_purchase_data": state.get("pending_purchase_data"),
            "missing_fields": state.get("missing_fields"),
            "query_result_during_flow": True
        }

    def build_workflow(self) -> StateGraph:
        """構建工作流程圖"""
        logger.info("Building SAP Agent workflow")
        
        # 創建工作流程圖
        workflow = StateGraph(State)
        
        # 添加節點
        workflow.add_node("format_question", self.format_question)
        workflow.add_node("purchase_history", self.handle_purchase_history)
        workflow.add_node("inventory", self.handle_inventory)
        workflow.add_node("purchase_request", self.handle_purchase_request)
        workflow.add_node("purchase_request_info_collection", self.handle_purchase_request_info_collection)
        workflow.add_node("purchase_request_confirmation", self.handle_purchase_request_confirmation)
        workflow.add_node("purchase_history_during_flow", self.handle_purchase_history_during_flow)
        workflow.add_node("inventory_during_flow", self.handle_inventory_during_flow)
        workflow.add_node("general_chat", self.handle_general_chat)
        workflow.add_node("generate_response", self.generate_response)
        
        # 設置起點
        workflow.add_edge(START, "format_question")
        
        # 添加條件邊
        workflow.add_conditional_edges(
            "format_question",
            self.route_agent,
            {
                "purchase_history": "purchase_history",
                "inventory": "inventory", 
                "purchase_request": "purchase_request",
                "purchase_request_info_collection": "purchase_request_info_collection",
                "purchase_request_confirmation": "purchase_request_confirmation",
                "purchase_history_during_flow": "purchase_history_during_flow",
                "inventory_during_flow": "inventory_during_flow",
                "general_chat": "general_chat"
            }
        )
        
        # 所有節點都連接到生成回應
        workflow.add_edge("purchase_history", "generate_response")
        workflow.add_edge("inventory", "generate_response")
        workflow.add_edge("purchase_request", "generate_response")
        workflow.add_edge("purchase_request_info_collection", "generate_response")
        workflow.add_edge("purchase_request_confirmation", "generate_response")
        workflow.add_edge("purchase_history_during_flow", "generate_response")
        workflow.add_edge("inventory_during_flow", "generate_response")
        workflow.add_edge("general_chat", "generate_response")
        
        # 設置終點
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()

    def chat(self, question: str, chat_history: Optional[List[Dict[str, str]]] = None) -> tuple[str, int]:
        """與 SAP Agent 對話"""
        try:
            # 構建工作流程
            app = self.build_workflow()
            
            # 準備初始狀態
            initial_state = {
                "question": question,
                "chat_history": chat_history or [],
                "documents": [],
                "generation": "",
                "api_data": None,
                "agent_type": "",
                "purchase_request_state": None,
                "pending_purchase_data": None
            }
            
            # 執行工作流程
            result = app.invoke(initial_state)
            
            # 提取回應和 token 計數（估算）
            response = result.get("generation", "抱歉，無法生成回應")
            token_count = len(response.split()) * 1.3  # 估算 token 數量
            
            # 結束串流
            if self._stream_q:
                self._stream_q.put("[[END]]")
            
            return response, int(token_count)
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            error_response = f"抱歉，處理您的請求時發生錯誤：{str(e)}"
            
            # 結束串流
            if self._stream_q:
                self._stream_q.put("[[END]]")
                
            return error_response, 0
