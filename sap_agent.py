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

        if purchase_state == "ready_to_create" and pending_data:
            # 有待創建的請購單，檢查用戶是否確認
            logger.info("ROUTE TO PURCHASE REQUEST CONFIRMATION")
            return "purchase_request_confirmation"
        elif purchase_state == "collecting_info":
            # 正在收集資訊
            logger.info("ROUTE TO PURCHASE REQUEST INFO COLLECTION")
            return "purchase_request_info_collection"

        question = state["formatted_question"]

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

    def get_available_purchase_categories(self) -> List[str]:
        """獲取所有可用的採購歷史產品類別"""
        try:
            api_data = self.api_client.get_purchase_history()
            if api_data.get("status") == "success" and "data" in api_data:
                categories = list(set(item["category"] for item in api_data["data"]))
                return categories
            return []
        except Exception as e:
            logger.error(f"Error fetching purchase categories: {e}")
            return []

    def analyze_user_intent_for_purchase_history(
        self, question: str, available_categories: List[str]
    ) -> Dict[str, Any]:
        """使用LLM分析使用者的採購歷史查詢意圖"""
        try:
            analysis_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", PURCHASE_HISTORY_INTENT_PROMPT),
                    ("human", "請分析這個問題"),
                ]
            )

            analysis_chain = analysis_prompt | self.llm | StrOutputParser()
            response = analysis_chain.invoke(
                {"available_categories": available_categories, "question": question}
            )

            # 嘗試解析JSON回應
            try:
                return json.loads(response.strip())
            except json.JSONDecodeError:
                # 如果JSON解析失敗，回傳預設值
                logger.warning("Failed to parse JSON response: %s", response)
                return {
                    "query_type": "all",
                    "category": None,
                    "supplier": None,
                    "start_date": None,
                    "end_date": None,
                    "product_keywords": [],
                }

        except Exception as e:
            logger.error("Error analyzing purchase history intent: %s", e)
            return {
                "query_type": "all",
                "category": None,
                "supplier": None,
                "start_date": None,
                "end_date": None,
                "product_keywords": [],
            }

    def handle_purchase_history(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理採購歷史查詢"""
        logger.info("HANDLE PURCHASE HISTORY")

        question = state["formatted_question"]

        # 獲取所有可用的產品類別
        available_categories = self.get_available_purchase_categories()
        logger.info(f"Available purchase categories: {available_categories}")

        # 使用LLM分析使用者意圖
        intent_analysis = self.analyze_user_intent_for_purchase_history(
            question, available_categories
        )
        logger.info(f"Purchase history intent analysis: {intent_analysis}")

        # 根據分析結果調用API
        api_data = None
        try:
            query_type = intent_analysis.get("query_type", "all")
            category = intent_analysis.get("category")
            supplier = intent_analysis.get("supplier")
            start_date = intent_analysis.get("start_date")
            end_date = intent_analysis.get("end_date")

            if query_type == "category" and category:
                # 確保類別在可用列表中
                if category in available_categories:
                    api_data = self.api_client.get_purchase_history(category=category)
                else:
                    # 如果指定的類別不存在，嘗試模糊匹配
                    matched_category = None
                    for avail_cat in available_categories:
                        if any(
                            keyword in avail_cat
                            for keyword in intent_analysis.get("product_keywords", [])
                        ):
                            matched_category = avail_cat
                            break

                    if matched_category:
                        api_data = self.api_client.get_purchase_history(
                            category=matched_category
                        )
                    else:
                        api_data = self.api_client.get_purchase_history()
            elif query_type == "supplier" and supplier:
                api_data = self.api_client.get_purchase_history(supplier=supplier)
            elif query_type == "date_range" and (start_date or end_date):
                api_data = self.api_client.get_purchase_history(
                    start_date=start_date, end_date=end_date
                )
            else:
                # 預設獲取所有採購歷史
                api_data = self.api_client.get_purchase_history()

        except Exception as e:
            logger.error(f"Error calling purchase history API: {e}")
            api_data = (
                self.api_client.get_purchase_history()
            )  # fallback to all purchase history

        return {"agent_type": "purchase_history", "api_data": api_data}

    def get_available_categories(self) -> List[str]:
        """獲取所有可用的產品類別"""
        try:
            api_data = self.api_client.get_inventory()
            if api_data.get("status") == "success" and "data" in api_data:
                categories = list(set(item["category"] for item in api_data["data"]))
                return categories
            return []
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return []

    def analyze_user_intent_for_inventory(
        self, question: str, available_categories: List[str]
    ) -> Dict[str, Any]:
        """使用LLM分析使用者的庫存查詢意圖"""
        try:
            analysis_prompt = ChatPromptTemplate.from_messages(
                [("system", INVENTORY_INTENT_PROMPT), ("human", "請分析這個問題")]
            )

            analysis_chain = analysis_prompt | self.llm | StrOutputParser()
            response = analysis_chain.invoke(
                {"available_categories": available_categories, "question": question}
            )

            # 嘗試解析JSON回應
            try:
                return json.loads(response.strip())
            except json.JSONDecodeError:
                # 如果JSON解析失敗，回傳預設值
                logger.warning("Failed to parse JSON response: %s", response)
                return {
                    "query_type": "all",
                    "category": None,
                    "low_stock_filter": False,
                    "product_keywords": [],
                    "location": None,
                }

        except Exception as e:
            logger.error("Error analyzing user intent: %s", e)
            return {
                "query_type": "all",
                "category": None,
                "low_stock_filter": False,
                "product_keywords": [],
                "location": None,
            }

    def handle_inventory(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理庫存查詢"""
        logger.info("HANDLE INVENTORY")

        question = state["formatted_question"]

        # 獲取所有可用的產品類別
        available_categories = self.get_available_categories()
        logger.info(f"Available categories: {available_categories}")

        # 使用LLM分析使用者意圖
        intent_analysis = self.analyze_user_intent_for_inventory(
            question, available_categories
        )
        logger.info(f"Intent analysis: {intent_analysis}")

        # 根據分析結果調用API
        api_data = None
        try:
            query_type = intent_analysis.get("query_type", "all")
            category = intent_analysis.get("category")
            low_stock_filter = intent_analysis.get("low_stock_filter", False)
            location = intent_analysis.get("location")

            if query_type == "low_stock" or low_stock_filter:
                api_data = self.api_client.get_inventory(low_stock=True)
            elif query_type == "category" and category:
                # 確保類別在可用列表中
                if category in available_categories:
                    api_data = self.api_client.get_inventory(category=category)
                else:
                    # 如果指定的類別不存在，嘗試模糊匹配
                    matched_category = None
                    for avail_cat in available_categories:
                        if any(
                            keyword in avail_cat
                            for keyword in intent_analysis.get("product_keywords", [])
                        ):
                            matched_category = avail_cat
                            break

                    if matched_category:
                        api_data = self.api_client.get_inventory(
                            category=matched_category
                        )
                    else:
                        api_data = self.api_client.get_inventory()
            elif location:
                api_data = self.api_client.get_inventory(location=location)
            else:
                # 預設獲取所有庫存
                api_data = self.api_client.get_inventory()

        except Exception as e:
            logger.error(f"Error calling inventory API: {e}")
            api_data = self.api_client.get_inventory()  # fallback to all inventory

        return {"agent_type": "inventory", "api_data": api_data}

    def check_purchase_request_state(self, state: Dict[str, Any]) -> str:
        """檢查請購單狀態並決定下一步路由"""
        logger.info("CHECK PURCHASE REQUEST STATE")

        # 檢查是否有待處理的請購單狀態
        purchase_state = state.get("purchase_request_state")
        pending_data = state.get("pending_purchase_data")

        if purchase_state == "ready_to_create" and pending_data:
            # 有待創建的請購單，檢查用戶是否確認
            logger.info("ROUTE TO PURCHASE REQUEST CONFIRMATION")
            return "purchase_request_confirmation"
        elif purchase_state == "collecting_info":
            # 正在收集資訊
            logger.info("ROUTE TO PURCHASE REQUEST INFO COLLECTION")
            return "purchase_request_info_collection"
        else:
            # 一般請購單處理
            logger.info("ROUTE TO PURCHASE REQUEST HANDLER")
            return "purchase_request_handler"

    def handle_purchase_request_confirmation(
        self, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """處理請購單確認"""
        logger.info("HANDLE PURCHASE REQUEST CONFIRMATION")

        user_response = state["question"]
        pending_data = state.get("pending_purchase_data", {})

        try:
            # 使用 LLM 分析用戶回應
            confirmation_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", PURCHASE_REQUEST_CONFIRMATION_PROMPT),
                    ("human", "請分析用戶回應"),
                ]
            )

            confirmation_chain = confirmation_prompt | self.llm | StrOutputParser()
            response = confirmation_chain.invoke(
                {
                    "pending_data": json.dumps(
                        pending_data, ensure_ascii=False, indent=2
                    ),
                    "user_response": user_response,
                }
            )

            logger.info(f"Confirmation analysis: {response}")

            # 解析回應
            if "CONFIRM_CREATE" in response:
                # 用戶確認創建請購單
                logger.info("User confirmed to create purchase request")
                api_data = self.api_client.create_purchase_request(pending_data)

                if api_data.get("status") == "success":
                    return {
                        "agent_type": "purchase_request_created",
                        "api_data": api_data,
                        "purchase_request_state": "completed",
                        "pending_purchase_data": None,
                    }
                else:
                    return {
                        "agent_type": "purchase_request_error",
                        "api_data": api_data,
                        "purchase_request_state": None,
                        "pending_purchase_data": None,
                    }

            elif "MODIFY_INFO" in response:
                # 用戶想要修改資訊
                logger.info("User wants to modify information")
                return {
                    "agent_type": "purchase_request_modify",
                    "api_data": {
                        "action": "modify",
                        "current_data": pending_data,
                        "user_request": user_response,
                    },
                    "purchase_request_state": "collecting_info",
                    "pending_purchase_data": pending_data,
                }

            elif "CANCEL" in response:
                # 用戶取消
                logger.info("User cancelled purchase request")
                return {
                    "agent_type": "purchase_request_cancelled",
                    "api_data": {"action": "cancelled"},
                    "purchase_request_state": None,
                    "pending_purchase_data": None,
                }

            else:
                # 需要更多資訊或不明確
                logger.info("Need more clarification")
                return {
                    "agent_type": "purchase_request_clarification",
                    "api_data": {"action": "clarify", "pending_data": pending_data},
                    "purchase_request_state": "ready_to_create",
                    "pending_purchase_data": pending_data,
                }

        except Exception as e:
            logger.error(f"Error in purchase request confirmation: {e}")
            return {
                "agent_type": "purchase_request_error",
                "api_data": {"status": "error", "message": str(e)},
                "purchase_request_state": None,
                "pending_purchase_data": None,
            }

    def handle_purchase_request_info_collection(
        self, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """處理請購單資訊收集"""
        logger.info("HANDLE PURCHASE REQUEST INFO COLLECTION")

        user_input = state["question"]
        existing_data = state.get("pending_purchase_data", {})
        history = self._format_history_to_string(state.get("chat_history"))

        try:
            # 使用 LLM 提取資訊
            info_collection_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", PURCHASE_REQUEST_INFO_COLLECTION_PROMPT),
                    ("human", "請提取資訊"),
                ]
            )

            info_chain = info_collection_prompt | self.llm | StrOutputParser()
            response = info_chain.invoke(
                {
                    "existing_data": json.dumps(
                        existing_data, ensure_ascii=False, indent=2
                    ),
                    "user_input": user_input,
                    "history": history,
                }
            )

            logger.info(f"Info extraction response: {response}")

            # 解析提取的資訊
            try:
                extracted_info = json.loads(response.strip())

                # 合併新資訊到現有資料
                updated_data = existing_data.copy()
                updated_data.update(extracted_info)

                # 檢查是否有足夠的必要資訊
                required_fields = [
                    "product_name",
                    "quantity",
                    "unit_price",
                    "requester",
                    "department",
                ]
                missing_fields = [
                    field for field in required_fields if not updated_data.get(field)
                ]

                if not missing_fields:
                    # 資訊完整，直接創建請購單
                    logger.info("All required information collected - Creating purchase request")

                    # 準備 API 調用的資料
                    api_data_for_creation = {
                        "product_name": updated_data["product_name"],
                        "category": updated_data.get("category", "3C產品"),
                        "quantity": int(updated_data["quantity"]),
                        "unit_price": float(updated_data["unit_price"]),
                        "requester": updated_data["requester"],
                        "department": updated_data.get("department", "未指定部門"),
                        "reason": updated_data.get("reason", "業務需求"),
                        "urgent": updated_data.get("urgent", False),
                        "expected_delivery_date": updated_data.get("expected_delivery_date", ""),
                    }

                    # 實際調用 API 創建請購單
                    api_result = self.api_client.create_purchase_request(api_data_for_creation)

                    if api_result.get("status") == "success":
                        return {
                            "agent_type": "purchase_request_created",
                            "api_data": api_result,
                            "purchase_request_state": "completed",
                            "pending_purchase_data": None,
                        }
                    else:
                        return {
                            "agent_type": "purchase_request_error",
                            "api_data": api_result,
                            "purchase_request_state": None,
                            "pending_purchase_data": None,
                        }
                else:
                    # 還缺少某些資訊
                    logger.info(f"Still missing fields: {missing_fields}")
                    return {
                        "agent_type": "purchase_request_incomplete",
                        "api_data": {
                            "action": "incomplete",
                            "missing_fields": missing_fields,
                            "current_data": updated_data,
                        },
                        "purchase_request_state": "collecting_info",
                        "pending_purchase_data": updated_data,
                    }

            except json.JSONDecodeError:
                logger.warning("Failed to parse extracted info JSON")
                return {
                    "agent_type": "purchase_request_parse_error",
                    "api_data": {"action": "parse_error", "response": response},
                    "purchase_request_state": "collecting_info",
                    "pending_purchase_data": existing_data,
                }

        except Exception as e:
            logger.error(f"Error in info collection: {e}")
            return {
                "agent_type": "purchase_request_error",
                "api_data": {"status": "error", "message": str(e)},
                "purchase_request_state": None,
                "pending_purchase_data": None,
            }

    def handle_purchase_request(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理請購單相關（重新設計）"""
        logger.info("HANDLE PURCHASE REQUEST")

        question = state["formatted_question"]
        original_question = state["question"]  # 使用原始問題，可能包含更多資訊
        history = self._format_history_to_string(state.get("chat_history"))

        # 檢查是否是創建請購單的請求
        if any(
            keyword in question for keyword in ["創建", "申請", "新", "購買", "訂購", "買"]
        ) or any(
            keyword in original_question for keyword in ["想要買", "要買", "購買", "申請", "採購"]
        ):
            logger.info("Starting purchase request creation process")

            # 使用 LLM 分析並提取初始資訊，同時使用原始問題和格式化問題
            try:
                info_collection_prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", PURCHASE_REQUEST_INFO_COLLECTION_PROMPT),
                        ("human", "請提取資訊"),
                    ]
                )

                info_chain = info_collection_prompt | self.llm | StrOutputParser()
                
                # 合併原始問題和格式化問題，提供更多上下文
                combined_input = f"原始問題: {original_question}\n格式化問題: {question}"
                
                response = info_chain.invoke(
                    {"existing_data": "{}", "user_input": combined_input, "history": history}
                )

                logger.info(f"Info extraction response from LLM: {response}")

                try:
                    extracted_info = json.loads(response.strip())
                    logger.info(f"Successfully parsed extracted info: {extracted_info}")

                    # 如果沒有提取到 product_name，嘗試手動解析
                    if not extracted_info.get("product_name"):
                        # 嘗試從問題中提取產品名稱
                        if "macbook" in original_question.lower():
                            if "air" in original_question.lower():
                                if "m4" in original_question.lower():
                                    extracted_info["product_name"] = "MacBook Air M4"
                                else:
                                    extracted_info["product_name"] = "MacBook Air"
                            elif "pro" in original_question.lower():
                                extracted_info["product_name"] = "MacBook Pro"
                            else:
                                extracted_info["product_name"] = "MacBook"
                        
                        # 確保有基本的數量
                        if not extracted_info.get("quantity"):
                            extracted_info["quantity"] = 1

                    logger.info(f"Final extracted info after manual parsing: {extracted_info}")

                    # 檢查是否有足夠的必要資訊
                    required_fields = [
                        "product_name",
                        "quantity",
                        "unit_price",
                        "requester",
                        "department",
                    ]
                    missing_fields = [
                        field
                        for field in required_fields
                        if not extracted_info.get(field)
                    ]

                    if not missing_fields:
                        # 資訊完整，直接創建請購單
                        logger.info("All required information collected in initial request - Creating purchase request")
                        
                        # 準備 API 調用的資料
                        api_data_for_creation = {
                            "product_name": extracted_info["product_name"],
                            "category": extracted_info.get("category", "3C產品"),
                            "quantity": int(extracted_info["quantity"]),
                            "unit_price": float(extracted_info["unit_price"]),
                            "requester": extracted_info["requester"],
                            "department": extracted_info.get("department", "未指定部門"),
                            "reason": extracted_info.get("reason", "業務需求"),
                            "urgent": extracted_info.get("urgent", False),
                            "expected_delivery_date": extracted_info.get("expected_delivery_date", ""),
                        }
                        
                        # 實際調用 API 創建請購單
                        logger.info(f"Calling API with data: {api_data_for_creation}")
                        api_result = self.api_client.create_purchase_request(api_data_for_creation)
                        logger.info(f"API result: {api_result}")
                        
                        if api_result.get("status") == "success":
                            return {
                                "agent_type": "purchase_request_created",
                                "api_data": api_result,
                                "purchase_request_state": "completed",
                                "pending_purchase_data": None,
                            }
                        else:
                            return {
                                "agent_type": "purchase_request_error",
                                "api_data": api_result,
                                "purchase_request_state": None,
                                "pending_purchase_data": None,
                            }
                    else:
                        # 還缺少某些資訊
                        logger.info(f"Missing required fields: {missing_fields}")
                        return {
                            "agent_type": "purchase_request_incomplete",
                            "api_data": {
                                "action": "incomplete",
                                "missing_fields": missing_fields,
                                "current_data": extracted_info,
                            },
                            "purchase_request_state": "collecting_info",
                            "pending_purchase_data": extracted_info,
                        }

                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}, response was: {response}")
                    # JSON 解析失敗，嘗試手動提取基本資訊
                    extracted_info = {}
                    
                    # 手動提取產品名稱
                    if "macbook" in original_question.lower():
                        if "air" in original_question.lower():
                            if "m4" in original_question.lower():
                                extracted_info["product_name"] = "MacBook Air M4"
                        else:
                            extracted_info["product_name"] = "MacBook Air"
                    elif "pro" in original_question.lower():
                        extracted_info["product_name"] = "MacBook Pro"
                    else:
                        extracted_info["product_name"] = "MacBook"
                    extracted_info["quantity"] = 1
                    
                    if extracted_info:
                        # 有基本資訊，進入收集模式
                        required_fields = [
                            "product_name",
                            "quantity",
                            "unit_price",
                            "requester",
                            "department",
                        ]
                        missing_fields = [
                            field
                            for field in required_fields
                            if not extracted_info.get(field)
                        ]
                        
                        return {
                            "agent_type": "purchase_request_incomplete",
                            "api_data": {
                                "action": "incomplete",
                                "missing_fields": missing_fields,
                                "current_data": extracted_info,
                            },
                            "purchase_request_state": "collecting_info",
                            "pending_purchase_data": extracted_info,
                        }
                    else:
                        # 完全沒有資訊，返回指導
                        return {
                            "agent_type": "purchase_request_guide",
                            "api_data": {
                                "action": "guide",
                                "message": "請提供以下資訊以創建請購單：產品名稱、數量、預估單價、申請人、部門",
                            },
                            "purchase_request_state": "collecting_info",
                            "pending_purchase_data": {},
                        }

            except Exception as e:
                logger.error(f"Error in initial info extraction: {e}")
                return {
                    "agent_type": "purchase_request_guide",
                    "api_data": {
                        "action": "guide",
                        "message": "請提供以下資訊以創建請購單：產品名稱、數量、預估單價、申請人、部門",
                    },
                    "purchase_request_state": "collecting_info",
                    "pending_purchase_data": {},
                }

        elif any(keyword in question for keyword in ["狀態", "進度", "追蹤"]):
            # 查詢請購單狀態
            api_data = self.api_client.get_all_purchase_requests()
            return {
                "agent_type": "purchase_request_query",
                "api_data": api_data,
                "purchase_request_state": None,
                "pending_purchase_data": None,
            }
        else:
            # 獲取所有請購單
            api_data = self.api_client.get_all_purchase_requests()
            return {
                "agent_type": "purchase_request_list",
                "api_data": api_data,
                "purchase_request_state": None,
                "pending_purchase_data": None,
            }

    def generate_response(self, state: Dict[str, Any]) -> Dict[str, str]:
        """生成回應"""
        logger.info("GENERATE RESPONSE")

        question = state["question"]
        formatted_question = state["formatted_question"]
        agent_type = state["agent_type"]
        api_data = state.get("api_data")
        history = self._format_history_to_string(state.get("chat_history"))

        try:
            with self._temp_stream():
                if agent_type == "purchase_history":
                    generation = self.purchase_history_chain.invoke(
                        {
                            "question": question,
                            "api_data": json.dumps(
                                api_data, ensure_ascii=False, indent=2
                            )
                            if api_data
                            else "無資料",
                            "history": history,
                        }
                    )
                elif agent_type == "inventory":
                    generation = self.inventory_chain.invoke(
                        {
                            "question": question,
                            "api_data": json.dumps(
                                api_data, ensure_ascii=False, indent=2
                            )
                            if api_data
                            else "無資料",
                            "history": history,
                        }
                    )
                elif agent_type.startswith("purchase_request"):
                    # 處理所有請購單相關的回應類型
                    if agent_type == "purchase_request_created":
                        # 請購單創建成功
                        if api_data and api_data.get("status") == "success":
                            request_id = api_data.get("data", {}).get("request_id", "未知")
                            generation = f"✅ 請購單創建成功！\n\n請購單編號：{request_id}\n狀態：待審核\n\n您可以使用請購單編號追蹤審核進度。如有任何問題，請聯繫相關部門主管。"
                        else:
                            generation = "❌ 請購單創建失敗，請稍後再試或聯繫系統管理員。"
                    
                    elif agent_type == "purchase_request_incomplete":
                        # 需要更多資訊
                        missing_fields = api_data.get("missing_fields", [])
                        current_data = api_data.get("current_data", {})
                        
                        field_names = {
                            "product_name": "產品名稱",
                            "quantity": "數量", 
                            "unit_price": "預估單價",
                            "requester": "申請人",
                            "department": "部門"
                        }
                        
                        missing_field_names = [field_names.get(field, field) for field in missing_fields]
                        
                        current_info = ""
                        if current_data:
                            current_info = "\n\n目前已收集到的資訊：\n"
                            for key, value in current_data.items():
                                if value:
                                    current_info += f"- {field_names.get(key, key)}：{value}\n"
                        
                        generation = f"請提供以下必要資訊以完成請購單申請：\n\n"
                        for field_name in missing_field_names:
                            generation += f"• {field_name}\n"
                        generation += current_info
                        generation += "\n請提供缺少的資訊，例如：\n申請人：張三\n部門：IT部門\n預估單價：50000"
                    
                    elif agent_type == "purchase_request_guide":
                        # 引導使用者
                        generation = "🛒 歡迎使用請購單申請系統！\n\n要創建請購單，請提供以下資訊：\n\n• 產品名稱（必要）\n• 數量（必要）\n• 預估單價（必要）\n• 申請人（必要）\n• 部門（必要）\n• 申請原因（選填）\n• 預期交付日期（選填）\n\n您可以按照以下格式提供：\n申請人 產品名稱 數量 價格 用途\n\n例如：\n廖柏瑜 MacBook Air M4 1 34900 工作需求"
                    
                    elif agent_type == "purchase_request_error":
                        # 錯誤處理
                        error_msg = api_data.get("message", "未知錯誤") if api_data else "系統錯誤"
                        generation = f"❌ 請購單處理發生錯誤：{error_msg}\n\n請檢查輸入資訊是否正確，或稍後再試。如問題持續，請聯繫系統管理員。"
                    
                    else:
                        # 其他請購單相關操作（查詢、列表等）
                        generation = self.purchase_request_chain.invoke(
                            {
                                "question": question,
                                "api_data": json.dumps(
                                    api_data, ensure_ascii=False, indent=2
                                )
                                if api_data
                                else "無資料",
                                "history": history,
                            }
                        )
                else:  # general_chat
                    generation = self.general_chat_chain.invoke(
                        {"question": question, "history": history}
                    )

            if self._stream_q is not None:
                self._stream_q.put("[[END]]")

            return {"generation": generation}

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_msg = "抱歉，處理您的請求時發生錯誤，請稍後再試。"

            if self._stream_q is not None:
                self._stream_text(error_msg)
                self._stream_q.put("[[END]]")

            return {"generation": error_msg}

    def build_workflow(self) -> StateGraph:
        """建立工作流程"""
        workflow = StateGraph(State)

        # Add nodes
        workflow.add_node("format_question", self.format_question)
        workflow.add_node("purchase_history", self.handle_purchase_history)
        workflow.add_node("inventory", self.handle_inventory)
        workflow.add_node("purchase_request", self.handle_purchase_request)
        workflow.add_node(
            "purchase_request_confirmation", self.handle_purchase_request_confirmation
        )
        workflow.add_node(
            "purchase_request_info_collection",
            self.handle_purchase_request_info_collection,
        )
        workflow.add_node("generate_response", self.generate_response)

        # Add edges
        workflow.add_edge(START, "format_question")

        # Add conditional routing
        workflow.add_conditional_edges(
            "format_question",
            self.route_agent,
            {
                "purchase_history": "purchase_history",
                "inventory": "inventory",
                "purchase_request": "purchase_request",
                "purchase_request_confirmation": "purchase_request_confirmation",
                "purchase_request_info_collection": "purchase_request_info_collection",
                "general_chat": "generate_response",
            },
        )

        workflow.add_edge("purchase_history", "generate_response")
        workflow.add_edge("inventory", "generate_response")
        workflow.add_edge("purchase_request", "generate_response")
        workflow.add_edge("purchase_request_confirmation", "generate_response")
        workflow.add_edge("purchase_request_info_collection", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow

    def chat(
        self, question: str, history: Optional[List[Dict[str, str]]] = None
    ) -> tuple[str, List[int]]:
        """主要的聊天接口"""
        if not history:
            history = []

        try:
            workflow = self.build_workflow()
            compiled_workflow = workflow.compile()

            start_time = time.time()

            # 從歷史對話中提取狀態信息（如果有的話）
            purchase_request_state = None
            pending_purchase_data = None

            # 檢查最近的對話是否包含請購單狀態信息
            for message in reversed(history[-10:]):  # 只檢查最近10條消息
                if message.get("role") == "assistant":
                    content = message.get("content", "")
                    if (
                        "請確認以上資訊是否正確" in content
                        and "沒有問題" not in question.lower()
                    ):
                        # 檢測到請購單確認狀態
                        purchase_request_state = "ready_to_create"
                        # 這裡可以更精確地提取pending_purchase_data，暫時先這樣處理
                        break
                    elif "請提供" in content and any(
                        field in content
                        for field in ["產品名稱", "數量", "單價", "申請人", "部門"]
                    ):
                        # 檢測到資訊收集狀態
                        purchase_request_state = "collecting_info"
                        pending_purchase_data = {}
                        break

            # Execute workflow
            result = compiled_workflow.invoke(
                {
                    "question": question,
                    "formatted_question": "",
                    "documents": [],
                    "generation": "",
                    "chat_history": history,
                    "api_data": None,
                    "agent_type": "",
                    "purchase_request_state": purchase_request_state,
                    "pending_purchase_data": pending_purchase_data,
                }
            )

            processing_time = time.time() - start_time
            logger.info(f"Total processing time: {processing_time:.2f}s")

            return result.get("generation", "抱歉，無法生成回應"), [
                0,
                0,
                0,
            ]  # Token count placeholder

        except Exception as e:
            logger.error(f"Chat error: {e}")
            error_msg = "抱歉，系統暫時無法處理您的請求，請稍後再試。"

            if self._stream_q is not None:
                self._stream_text(error_msg)
                self._stream_q.put("[[END]]")

            return error_msg, [0, 0, 0]
