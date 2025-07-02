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
            analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", PURCHASE_HISTORY_INTENT_PROMPT),
                ("human", "請分析這個問題")
            ])
            
            analysis_chain = analysis_prompt | self.llm | StrOutputParser()
            response = analysis_chain.invoke({
                "available_categories": available_categories,
                "question": question
            })
            
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
                    "product_keywords": []
                }
                
        except Exception as e:
            logger.error("Error analyzing purchase history intent: %s", e)
            return {
                "query_type": "all",
                "category": None,
                "supplier": None,
                "start_date": None,
                "end_date": None,
                "product_keywords": []
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
            analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", INVENTORY_INTENT_PROMPT),
                ("human", "請分析這個問題")
            ])
            
            analysis_chain = analysis_prompt | self.llm | StrOutputParser()
            response = analysis_chain.invoke({
                "available_categories": available_categories,
                "question": question
            })
            
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
                    "location": None
                }
                
        except Exception as e:
            logger.error("Error analyzing user intent: %s", e)
            return {
                "query_type": "all",
                "category": None,
                "low_stock_filter": False,
                "product_keywords": [],
                "location": None
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

    def handle_purchase_request(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """處理請購單相關"""
        logger.info("HANDLE PURCHASE REQUEST")

        question = state["formatted_question"]

        # 根據問題內容決定操作
        if "創建" in question or "申請" in question or "新" in question:
            # 這裡可能需要進一步分析是否有足夠資訊創建請購單
            # 暫時返回創建請購單的指導
            api_data = {
                "action": "create_guide",
                "message": "請提供以下資訊以創建請購單：產品名稱、數量、預估單價、申請人、部門",
            }
        elif "狀態" in question or "進度" in question or "追蹤" in question:
            # 查詢請購單狀態
            api_data = self.api_client.get_all_purchase_requests()
        else:
            # 獲取所有請購單
            api_data = self.api_client.get_all_purchase_requests()

        return {"agent_type": "purchase_request", "api_data": api_data}

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
                elif agent_type == "purchase_request":
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
                "general_chat": "generate_response",
            },
        )

        workflow.add_edge("purchase_history", "generate_response")
        workflow.add_edge("inventory", "generate_response")
        workflow.add_edge("purchase_request", "generate_response")
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
