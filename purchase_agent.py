"""
SAP 請購系統 AI Agent

這個系統的主要功能：
1. 接收使用者的請購需求
2. 呼叫採購歷史 API 分析歷史資料
3. 使用 LLM 推薦合適的產品規格
4. 創建請購單並透過 API 提交
"""

import os
import json
import requests
import queue
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph

# 導入自定義模組
from choose_state import PurchaseRequestState
from prompts import PurchasePrompts

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PurchaseAgentConfig:
    """請購 Agent 配置"""

    api_base_url: str = "http://localhost:7777"
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.3
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"


class PurchaseAgent:
    """請購系統 AI Agent"""

    def __init__(self, config: PurchaseAgentConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model_name=config.model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        self._stream_queue: Optional[queue.Queue] = None
        self._setup_prompts()
        self._setup_chains()
        self._setup_workflow()

    def _setup_prompts(self):
        """設定各種提示模板"""
        self.analyze_request_prompt = PurchasePrompts.get_analyze_request_prompt()
        self.recommend_product_prompt = PurchasePrompts.get_recommend_product_prompt()
        self.create_order_prompt = PurchasePrompts.get_create_order_prompt()

    def _setup_chains(self):
        """設定 LangChain 鏈"""
        self.analyze_chain = self.analyze_request_prompt | self.llm | StrOutputParser()
        self.recommend_chain = (
            self.recommend_product_prompt | self.llm | StrOutputParser()
        )
        self.create_order_chain = (
            self.create_order_prompt | self.llm | JsonOutputParser()
        )

    def _setup_workflow(self):
        """設定工作流程"""
        workflow = StateGraph(PurchaseRequestState)

        # 添加節點
        workflow.add_node("analyze_request", self.analyze_request)
        workflow.add_node("fetch_history", self.fetch_purchase_history)
        workflow.add_node("recommend_product", self.recommend_product)
        workflow.add_node("create_purchase_order", self.create_purchase_order)
        workflow.add_node("submit_order", self.submit_purchase_order)
        workflow.add_node("final_response", self.generate_final_response)

        # 設定邊緣和條件
        workflow.add_edge(START, "analyze_request")
        workflow.add_edge("analyze_request", "fetch_history")
        workflow.add_edge("fetch_history", "recommend_product")
        workflow.add_conditional_edges(
            "recommend_product",
            self.check_user_approval,
            {
                "approved": "create_purchase_order",
                "rejected": "recommend_product",
                "needs_clarification": "recommend_product",
            },
        )
        workflow.add_edge("create_purchase_order", "submit_order")
        workflow.add_edge("submit_order", "final_response")
        workflow.add_edge("final_response", END)

        self.workflow = workflow.compile()

    def attach_stream_queue(self, q: queue.Queue):
        """附加串流佇列"""
        self._stream_queue = q

    def _stream_text(self, text: str):
        """串流文字到佇列"""
        if self._stream_queue:
            for char in text:
                self._stream_queue.put(char)

    def analyze_request(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """分析使用者請購需求"""
        logger.info("分析使用者請購需求")

        try:
            analysis = self.analyze_chain.invoke(
                {"user_request": state["user_request"]}
            )

            self._stream_text(f"📋 需求分析：\n{analysis}\n\n")

            return {"current_step": "需求分析完成", "analysis": analysis}
        except requests.RequestException as e:
            logger.error("需求分析失敗: %s", e)
            return {"current_step": "需求分析失敗", "error": str(e)}
        except ValueError as e:
            logger.error("需求分析失敗: %s", e)
            return {"current_step": "需求分析失敗", "error": str(e)}

    def fetch_purchase_history(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """獲取採購歷史資料"""
        logger.info("獲取採購歷史資料")

        try:
            # 呼叫採購歷史 API
            response = requests.get(
                f"{self.config.api_base_url}/api/purchase-history", timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                purchase_history = data.get("data", [])

                self._stream_text(
                    f"📊 已獲取 {len(purchase_history)} 筆採購歷史資料\n\n"
                )

                return {
                    "purchase_history": purchase_history,
                    "current_step": "採購歷史獲取完成",
                }
            else:
                logger.error("API 呼叫失敗: %s", response.status_code)
                return {
                    "purchase_history": [],
                    "current_step": "採購歷史獲取失敗",
                    "error": f"API 呼叫失敗: {response.status_code}",
                }
        except requests.RequestException as e:
            logger.error("獲取採購歷史失敗: %s", e)
            return {
                "purchase_history": [],
                "current_step": "採購歷史獲取失敗",
                "error": str(e),
            }

    def recommend_product(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """推薦產品規格"""
        logger.info("推薦產品規格")

        try:
            # 格式化採購歷史資料
            history_text = ""
            for item in state.get("purchase_history", [])[:10]:  # 限制前10筆
                history_text += f"""
                產品: {item.get("product_name", "N/A")}
                類別: {item.get("category", "N/A")}
                供應商: {item.get("supplier", "N/A")}
                數量: {item.get("quantity", "N/A")}
                單價: NT$ {item.get("unit_price", "N/A"):,}
                購買日期: {item.get("purchase_date", "N/A")}
                部門: {item.get("department", "N/A")}
                ---
                """

            recommendation = self.recommend_chain.invoke(
                {
                    "user_request": state["user_request"],
                    "purchase_history": history_text,
                }
            )

            self._stream_text(f"🎯 產品推薦：\n{recommendation}\n\n")
            self._stream_text("請確認是否同意此推薦？(輸入 '同意' 或 '不同意')\n")

            return {"recommendations": recommendation, "current_step": "等待使用者確認"}
        except requests.RequestException as e:
            logger.error("產品推薦失敗: %s", e)
            return {
                "recommendations": "",
                "current_step": "產品推薦失敗",
                "error": str(e),
            }
        except ValueError as e:
            logger.error("產品推薦失敗: %s", e)
            return {
                "recommendations": "",
                "current_step": "產品推薦失敗",
                "error": str(e),
            }

    def check_user_approval(self, state: PurchaseRequestState) -> str:
        """檢查使用者是否同意推薦"""
        # 這裡需要等待使用者輸入，實際實作中可能需要不同的機制
        # 為了演示，我們假設使用者同意
        return "approved"

    def create_purchase_order(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """創建請購單"""
        logger.info("創建請購單")

        try:
            # 預設使用者資訊（實際應用中應該從認證系統獲取）
            user_info = {"requester": "系統使用者", "department": "IT部門"}

            order_data = self.create_order_chain.invoke(
                {
                    "recommendation": state["recommendations"],
                    "user_info": json.dumps(user_info, ensure_ascii=False),
                }
            )

            self._stream_text(
                f"📋 請購單已創建：\n{json.dumps(order_data, ensure_ascii=False, indent=2)}\n\n"
            )

            return {"purchase_order": order_data, "current_step": "請購單創建完成"}
        except requests.RequestException as e:
            logger.error("請購單創建失敗: %s", e)
            return {
                "purchase_order": {},
                "current_step": "請購單創建失敗",
                "error": str(e),
            }
        except ValueError as e:
            logger.error("請購單創建失敗: %s", e)
            return {
                "purchase_order": {},
                "current_step": "請購單創建失敗",
                "error": str(e),
            }

    def submit_purchase_order(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """提交請購單到 API"""
        logger.info("提交請購單")

        try:
            order_data = state["purchase_order"]

            # 處理可能的嵌套結構 - 如果 AI 生成了包含 purchase_order 列表的結構
            if isinstance(order_data, dict) and "purchase_order" in order_data:
                # 取第一個請購單項目
                if (
                    isinstance(order_data["purchase_order"], list)
                    and len(order_data["purchase_order"]) > 0
                ):
                    order_data = order_data["purchase_order"][0]
                else:
                    order_data = order_data["purchase_order"]

            # 確保日期格式正確（如果是2023年的日期，更新為2025年）
            if "expected_delivery_date" in order_data:
                delivery_date = order_data["expected_delivery_date"]
                if delivery_date.startswith("2023"):
                    order_data["expected_delivery_date"] = delivery_date.replace(
                        "2023", "2025"
                    )

            # 呼叫請購單 API
            response = requests.post(
                f"{self.config.api_base_url}/api/purchase-request",
                json=order_data,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 201:
                api_response = response.json()
                request_id = api_response.get("request_id")

                self._stream_text("✅ 請購單提交成功！\n")
                self._stream_text(f"請購單號：{request_id}\n")
                self._stream_text(
                    f"狀態：{api_response.get('data', {}).get('status', 'N/A')}\n\n"
                )

                return {"api_response": api_response, "current_step": "請購單提交成功"}
            else:
                logger.error("API 提交失敗: %s", response.status_code)
                return {
                    "api_response": {"error": f"API 提交失敗: {response.status_code}"},
                    "current_step": "請購單提交失敗",
                }
        except requests.RequestException as e:
            logger.error("請購單提交失敗: %s", e)
            return {"api_response": {"error": str(e)}, "current_step": "請購單提交失敗"}

    def generate_final_response(self, state: PurchaseRequestState) -> Dict[str, Any]:
        """生成最終回應"""
        logger.info("生成最終回應")

        # 檢查是否有成功的 API 回應
        api_response = state.get("api_response", {})
        purchase_order = state.get("purchase_order", {})

        logger.info("API 回應: %s", api_response)
        logger.info("請購單: %s", purchase_order)

        if api_response.get("request_id"):
            request_id = api_response["request_id"]
            product_name = purchase_order.get("product_name", "N/A")
            quantity = purchase_order.get("quantity", 0)
            unit_price = purchase_order.get("unit_price", 0)
            total_amount = unit_price * quantity if unit_price and quantity else 0

            final_msg = f"""
            🎉 請購流程完成！

            📄 請購單詳情：
            - 請購單號：{request_id}
            - 產品：{product_name}
            - 數量：{quantity}
            - 預估金額：NT$ {total_amount:,}

            您可以使用請購單號查詢審核進度。
            """
        else:
            # 檢查是否有錯誤訊息
            error_info = ""
            if api_response.get("error"):
                error_info = f"\n錯誤詳情：{api_response['error']}"

            final_msg = f"""
            ❌ 請購流程未完成

            請檢查以下可能的問題：
            1. 網路連線是否正常
            2. API 服務是否正在運行
            3. 請購資料是否完整{error_info}

            請重新嘗試或聯絡系統管理員。
            """

        self._stream_text(final_msg)

        if self._stream_queue:
            self._stream_queue.put("[[END]]")

        return {"generation": final_msg}

    def process_purchase_request(
        self, user_request: str, chat_history: Optional[List[Dict]] = None
    ) -> Tuple[Dict[str, Any], List[int]]:
        """處理請購請求"""

        if not chat_history:
            chat_history = []

        # 初始化狀態
        initial_state = {
            "user_request": user_request,
            "purchase_history": [],
            "recommendations": "",
            "user_approval": False,
            "purchase_order": {},
            "api_response": {},
            "chat_history": chat_history,
            "current_step": "開始處理",
        }

        try:
            # 執行工作流程
            result = self.workflow.invoke(initial_state)

            # 簡化的 token 計算（實際應用中需要更精確的計算）
            token_count = [100, 80, 20]  # [total, prompt, completion]

            return result, token_count

        except requests.RequestException as e:
            logger.error("處理請購請求失敗: %s", e)
            error_msg = f"處理請購請求時發生錯誤：{str(e)}"
            self._stream_text(error_msg)

            if self._stream_queue:
                self._stream_queue.put("[[END]]")

            return {"generation": error_msg}, [0, 0, 0]
        except ValueError as e:
            logger.error("處理請購請求失敗: %s", e)
            error_msg = f"處理請購請求時發生錯誤：{str(e)}"
            self._stream_text(error_msg)

            if self._stream_queue:
                self._stream_queue.put("[[END]]")

            return {"generation": error_msg}, [0, 0, 0]
