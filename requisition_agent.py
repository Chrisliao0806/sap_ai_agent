"""
SAP 採購專員 AI Agent

這個系統的主要功能：
1. 審核請購單狀態
2. 分析採購歷史和庫存資訊
3. 決定是否創建採購單
4. 創建和確認採購單
5. 更新請購單狀態
"""

import json
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_openai import ChatOpenAI

# 導入自定義模組
from choose_state import ConversationState
from prompts import PurchasePrompts

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RequisitionAgentConfig:
    """採購專員 Agent 配置"""

    api_base_url: str = "http://localhost:7777"
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.3
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_procurement_officer: str = "採購專員"
    default_department: str = "採購部"

    def __post_init__(self):
        # 如果沒有設定 openai_api_key，從環境變量獲取
        if not self.openai_api_key:
            import os

            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")


class RequisitionAgent:
    """採購專員 AI Agent"""

    def __init__(self, config: RequisitionAgentConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model_name=config.model,
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        self._setup_chains()
        self._session_states: Dict[str, Dict] = {}  # 儲存會話狀態

    def _setup_chains(self):
        """設定 LangChain 鏈"""
        self.intent_chain = (
            PurchasePrompts.get_requisition_intent_classification_prompt()
            | self.llm
            | JsonOutputParser()
        )
        self.decision_analysis_chain = (
            PurchasePrompts.get_purchase_decision_analysis_prompt()
            | self.llm
            | JsonOutputParser()
        )
        self.create_purchase_order_chain = (
            PurchasePrompts.get_create_purchase_order_prompt()
            | self.llm
            | JsonOutputParser()
        )
        self.guidance_chain = (
            PurchasePrompts.get_requisition_guidance_prompt()
            | self.llm
            | StrOutputParser()
        )
        self.status_validation_chain = (
            PurchasePrompts.get_purchase_request_status_validation_prompt()
            | self.llm
            | JsonOutputParser()
        )

    def _get_session_state(self, session_id: str) -> Dict:
        """獲取會話狀態"""
        if session_id not in self._session_states:
            self._session_states[session_id] = {
                "conversation_state": ConversationState.INITIAL,
                "current_request": None,
                "pending_requests": [],
                "purchase_history": [],
                "inventory_data": [],
                "decision_analysis": None,
                "purchase_order": None,
                "chat_history": [],
                "user_context": {
                    "officer": self.config.default_procurement_officer,
                    "department": self.config.default_department,
                },
            }
        return self._session_states[session_id]

    def _update_session_state(self, session_id: str, updates: Dict):
        """更新會話狀態"""
        state = self._get_session_state(session_id)
        state.update(updates)
        self._session_states[session_id] = state

    def _add_to_chat_history(self, session_id: str, role: str, content: str):
        """添加到對話歷史"""
        state = self._get_session_state(session_id)
        state["chat_history"].append({"role": role, "content": content})
        if len(state["chat_history"]) > 20:  # 保持最近20條對話
            state["chat_history"] = state["chat_history"][-20:]

    def _classify_intent(self, user_input: str, session_id: str) -> Dict:
        """分類採購專員意圖"""
        state = self._get_session_state(session_id)

        try:
            chat_history_str = "\n".join(
                [
                    f"{msg['role']}: {msg['content']}"
                    for msg in state["chat_history"][-5:]  # 最近5條對話
                ]
            )

            intent_result = self.intent_chain.invoke(
                {
                    "current_state": state["conversation_state"],
                    "user_input": user_input,
                    "chat_history": chat_history_str,
                }
            )

            return intent_result
        except Exception as e:
            logger.error(f"意圖分類失敗: {e}")
            return {
                "intent": "unclear",
                "next_state": "initial",
                "is_procurement_related": False,
                "guidance_message": "抱歉，我無法理解您的需求。請告訴我您想要處理哪個請購單？",
            }

    def _fetch_pending_requests(self) -> List[Dict]:
        """獲取待審核的請購單"""
        try:
            response = requests.get(
                f"{self.config.api_base_url}/api/purchase-requests",
                params={"status": "待審核"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.error(f"獲取請購單失敗: {response.status_code}")
                return []
        except requests.RequestException as e:
            logger.error(f"獲取請購單失敗: {e}")
            return []

    def _fetch_purchase_request(self, request_id: str) -> Optional[Dict]:
        """獲取特定請購單"""
        try:
            response = requests.get(
                f"{self.config.api_base_url}/api/purchase-request/{request_id}",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            else:
                logger.error(f"獲取請購單 {request_id} 失敗: {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.error(f"獲取請購單 {request_id} 失敗: {e}")
            return None

    def _fetch_purchase_history(self, product_name: str = None) -> List[Dict]:
        """獲取採購歷史資料"""
        try:
            params = {}
            if product_name:
                # 簡單的關鍵字搜尋
                params["product_name"] = product_name

            response = requests.get(
                f"{self.config.api_base_url}/api/purchase-history",
                params=params,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
            else:
                logger.error(f"獲取採購歷史失敗: {response.status_code}")
                return []
        except requests.RequestException as e:
            logger.error(f"獲取採購歷史失敗: {e}")
            return []

    def _fetch_inventory_data(self, product_name: str = None) -> List[Dict]:
        """獲取庫存資訊"""
        try:
            params = {}
            if product_name:
                # 簡單的關鍵字搜尋
                params["product_name"] = product_name

            response = requests.get(
                f"{self.config.api_base_url}/api/inventory",
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                inventory_data = data.get("data", [])

                # 如果有產品名稱，進行過濾
                if product_name:
                    filtered_data = []
                    for item in inventory_data:
                        if product_name.lower() in item.get("product_name", "").lower():
                            filtered_data.append(item)
                    return filtered_data

                return inventory_data
            else:
                logger.error(f"獲取庫存資訊失敗: {response.status_code}")
                return []
        except requests.RequestException as e:
            logger.error(f"獲取庫存資訊失敗: {e}")
            return []

    def _handle_review_requests(self, user_input: str, session_id: str) -> str:
        """處理審核請購單"""
        try:
            # 獲取待審核的請購單
            pending_requests = self._fetch_pending_requests()

            if not pending_requests:
                return "目前沒有待審核的請購單。"

            # 更新會話狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.REVIEWING_REQUESTS,
                    "pending_requests": pending_requests,
                },
            )

            # 格式化顯示請購單列表
            requests_display = "📋 待審核的請購單列表：\n\n"
            for i, req in enumerate(pending_requests, 1):
                total_amount = req.get("unit_price", 0) * req.get("quantity", 0)
                requests_display += (
                    f"{i}. **請購單號**: {req.get('request_id', 'N/A')}\n"
                )
                requests_display += f"   產品: {req.get('product_name', 'N/A')}\n"
                requests_display += f"   數量: {req.get('quantity', 0)}\n"
                requests_display += f"   單價: NT$ {req.get('unit_price', 0):,}\n"
                requests_display += f"   總金額: NT$ {total_amount:,}\n"
                requests_display += f"   請購人: {req.get('requester', 'N/A')}\n"
                requests_display += f"   部門: {req.get('department', 'N/A')}\n"
                requests_display += f"   狀態: {req.get('status', 'N/A')}\n\n"

            requests_display += (
                "請輸入請購單號來進行詳細審核，例如：「審核 PR20250107ABCDEF」"
            )

            return requests_display

        except Exception as e:
            logger.error(f"處理審核請購單失敗: {e}")
            return f"抱歉，獲取請購單時發生錯誤：{str(e)}"

    def _handle_analyze_purchase_decision(
        self, user_input: str, session_id: str
    ) -> str:
        """處理採購決策分析"""
        try:
            # 從用戶輸入中提取請購單號
            request_id = self._extract_request_id(user_input)

            if not request_id:
                return "請提供請購單號，例如：「審核 PR20250107ABCDEF」"

            # 獲取請購單資訊
            purchase_request = self._fetch_purchase_request(request_id)

            if not purchase_request:
                return f"找不到請購單 {request_id}，請檢查請購單號是否正確。"

            # 使用 LLM 進行狀態驗證，而不是硬編碼檢查
            request_info = self._format_purchase_request(purchase_request)
            
            try:
                status_validation = self.status_validation_chain.invoke(
                    {"purchase_request_info": request_info}
                )
                
                # 如果不能審核，返回 LLM 提供的訊息
                if not status_validation.get("can_review", False):
                    return status_validation.get("user_message", "此請購單目前無法進行審核。")
                    
            except Exception as e:
                logger.error(f"狀態驗證失敗: {e}")
                # 如果 LLM 驗證失敗，回退到基本檢查
                if purchase_request.get("status") == "已完成":
                    return f"請購單 {request_id} 已經處理完成，無需再次審核。"

            # 獲取相關的採購歷史和庫存資訊
            product_name = purchase_request.get("product_name", "")
            purchase_history = self._fetch_purchase_history(product_name)
            inventory_data = self._fetch_inventory_data(product_name)

            # 格式化資料供 LLM 分析
            history_info = self._format_purchase_history(purchase_history)
            inventory_info = self._format_inventory_data(inventory_data)

            # 使用 LLM 進行採購決策分析
            decision_analysis = self.decision_analysis_chain.invoke(
                {
                    "purchase_request": request_info,
                    "purchase_history": history_info,
                    "inventory_data": inventory_info,
                }
            )

            # 更新會話狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.ANALYZING_PURCHASE_DECISION,
                    "current_request": purchase_request,
                    "purchase_history": purchase_history,
                    "inventory_data": inventory_data,
                    "decision_analysis": decision_analysis,
                },
            )

            # 格式化顯示分析結果
            analysis_display = f"📊 採購決策分析報告 - 請購單號: {request_id}\n\n"
            analysis_display += f"🔍 **庫存狀況**: {decision_analysis.get('analysis_result', {}).get('inventory_status', 'N/A')}\n\n"
            analysis_display += f"💰 **價格比較**: {decision_analysis.get('analysis_result', {}).get('price_comparison', 'N/A')}\n\n"
            analysis_display += f"📋 **採購建議**: {decision_analysis.get('analysis_result', {}).get('recommendation', 'N/A')}\n\n"
            analysis_display += f"📝 **詳細說明**: {decision_analysis.get('detailed_explanation', 'N/A')}\n\n"
            analysis_display += (
                f"⚠️ **風險評估**: {decision_analysis.get('risk_assessment', 'N/A')}\n\n"
            )

            should_create = decision_analysis.get("should_create_purchase_order", False)

            if should_create:
                analysis_display += "✅ **建議**: 可以創建採購單\n\n"
                analysis_display += (
                    "請輸入「確認創建採購單」來繼續，或輸入「取消」來結束審核。"
                )
            else:
                analysis_display += "❌ **建議**: 不建議創建採購單\n\n"
                analysis_display += (
                    "請輸入「強制創建採購單」來強制創建，或輸入「取消」來結束審核。"
                )

            return analysis_display

        except Exception as e:
            logger.error(f"處理採購決策分析失敗: {e}")
            return f"抱歉，分析採購決策時發生錯誤：{str(e)}"

    def _handle_create_purchase_order(self, user_input: str, session_id: str) -> str:
        """處理創建採購單"""
        try:
            state = self._get_session_state(session_id)
            purchase_request = state.get("current_request")
            decision_analysis = state.get("decision_analysis")

            if not purchase_request or not decision_analysis:
                return "請先進行採購決策分析。"

            # 格式化資料供 LLM 創建採購單
            request_info = self._format_purchase_request(purchase_request)
            analysis_info = json.dumps(decision_analysis, ensure_ascii=False)

            # 使用 LLM 創建採購單
            purchase_order = self.create_purchase_order_chain.invoke(
                {
                    "purchase_request": request_info,
                    "decision_analysis": analysis_info,
                }
            )

            # 更新會話狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.CREATING_PURCHASE_ORDER,
                    "purchase_order": purchase_order,
                },
            )

            # 格式化顯示採購單
            order_display = "📋 採購單預覽\n\n"
            order_display += f"供應商ID: {purchase_order.get('supplier_id', 'N/A')}\n"
            order_display += f"產品名稱: {purchase_order.get('product_name', 'N/A')}\n"
            order_display += f"產品類別: {purchase_order.get('category', 'N/A')}\n"
            order_display += f"數量: {purchase_order.get('quantity', 0)}\n"
            order_display += f"單價: NT$ {purchase_order.get('unit_price', 0):,}\n"
            order_display += f"總金額: NT$ {purchase_order.get('quantity', 0) * purchase_order.get('unit_price', 0):,}\n"
            order_display += f"請購人: {purchase_order.get('requester', 'N/A')}\n"
            order_display += f"部門: {purchase_order.get('department', 'N/A')}\n\n"

            order_display += "請確認是否執行採購單創建？\n"
            order_display += "- 輸入「確認執行」來創建採購單並更新請購單狀態\n"
            order_display += "- 輸入「取消」來取消創建"

            return order_display

        except Exception as e:
            logger.error(f"處理創建採購單失敗: {e}")
            return f"抱歉，創建採購單時發生錯誤：{str(e)}"

    def _handle_confirm_purchase_order(self, user_input: str, session_id: str) -> str:
        """處理確認採購單"""
        user_input_lower = user_input.lower().strip()

        if any(keyword in user_input_lower for keyword in ["確認執行", "確認", "執行"]):
            return self._execute_purchase_order(session_id)
        elif any(keyword in user_input_lower for keyword in ["取消", "不要", "放棄"]):
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.INITIAL,
                    "current_request": None,
                    "decision_analysis": None,
                    "purchase_order": None,
                },
            )
            return "已取消採購單創建。如果您需要審核其他請購單，請重新開始。"
        else:
            return (
                "請明確回答：\n- 輸入「確認執行」來創建採購單\n- 輸入「取消」來取消創建"
            )

    def _execute_purchase_order(self, session_id: str) -> str:
        """執行採購單創建"""
        try:
            state = self._get_session_state(session_id)
            purchase_order = state.get("purchase_order")
            purchase_request = state.get("current_request")

            if not purchase_order or not purchase_request:
                return "缺少必要資訊，無法創建採購單。"

            request_id = purchase_request.get("request_id")

            # 調用 API 創建採購單
            response = requests.post(
                f"{self.config.api_base_url}/api/purchase-order/from-request/{request_id}",
                json=purchase_order,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code == 201:
                api_response = response.json()
                order_id = api_response.get("order_id")

                # 更新會話狀態
                self._update_session_state(
                    session_id,
                    {
                        "conversation_state": ConversationState.PURCHASE_ORDER_COMPLETED,
                        "api_response": api_response,
                    },
                )

                success_msg = f"✅ 採購單創建成功！\n\n"
                success_msg += f"📄 採購單詳情：\n"
                success_msg += f"- 採購單號：{order_id}\n"
                success_msg += f"- 請購單號：{request_id}\n"
                success_msg += f"- 產品：{purchase_order.get('product_name', 'N/A')}\n"
                success_msg += f"- 數量：{purchase_order.get('quantity', 0)}\n"
                success_msg += f"- 總金額：NT$ {purchase_order.get('quantity', 0) * purchase_order.get('unit_price', 0):,}\n"
                success_msg += (
                    f"- 供應商ID：{purchase_order.get('supplier_id', 'N/A')}\n\n"
                )
                success_msg += f"📋 請購單狀態已更新為「已完成」\n\n"
                success_msg += "如果您需要審核其他請購單，請重新開始。"

                return success_msg
            else:
                logger.error(f"API 創建採購單失敗: {response.status_code}")
                return f"❌ 創建採購單失敗\n\nAPI 錯誤：{response.status_code}\n請稍後重試或聯絡系統管理員。"

        except requests.RequestException as e:
            logger.error(f"執行採購單創建失敗: {e}")
            return (
                f"❌ 創建採購單失敗\n\n網路錯誤：{str(e)}\n請檢查網路連線或稍後重試。"
            )

    def _handle_off_topic(self, user_input: str, session_id: str) -> str:
        """處理偏離主題的對話"""
        try:
            state = self._get_session_state(session_id)
            guidance = self.guidance_chain.invoke(
                {"user_input": user_input, "current_state": state["conversation_state"]}
            )
            return guidance
        except Exception as e:
            logger.error(f"生成引導訊息失敗: {e}")
            return "我是專門協助您處理採購審核相關事務的助手。請告訴我您想要審核哪個請購單？"

    def _extract_request_id(self, user_input: str) -> Optional[str]:
        """從用戶輸入中提取請購單號"""
        import re

        # 更靈活的請購單號提取邏輯
        # 尋找 PR 開頭的請購單號 (支援多種格式)
        patterns = [
            r"PR\d{8}[A-Z0-9]{6}",  # 原始格式：PR20250107ABCDEF
            r"PR\d{8}[A-Z0-9]{5,8}",  # 彈性格式：PR20250707655A22
            r"PR\d{6,8}[A-Z0-9]{4,8}",  # 更彈性的格式
        ]

        for pattern in patterns:
            match = re.search(pattern, user_input.upper())
            if match:
                return match.group(0)

        # 如果找不到標準格式，嘗試從輸入中提取任何看起來像請購單號的內容
        # 尋找任何以 PR 開頭的字串
        pr_match = re.search(r"PR[A-Z0-9]{8,}", user_input.upper())
        if pr_match:
            return pr_match.group(0)

        return None

    def _format_purchase_request(self, purchase_request: Dict) -> str:
        """格式化請購單資訊"""
        return f"""
請購單號: {purchase_request.get("request_id", "N/A")}
產品名稱: {purchase_request.get("product_name", "N/A")}
產品類別: {purchase_request.get("category", "N/A")}
數量: {purchase_request.get("quantity", 0)}
單價: NT$ {purchase_request.get("unit_price", 0):,}
總金額: NT$ {purchase_request.get("total_amount", 0):,}
請購人: {purchase_request.get("requester", "N/A")}
部門: {purchase_request.get("department", "N/A")}
請購理由: {purchase_request.get("reason", "N/A")}
是否緊急: {"是" if purchase_request.get("urgent", False) else "否"}
預期交貨日期: {purchase_request.get("expected_delivery_date", "N/A")}
狀態: {purchase_request.get("status", "N/A")}
創建日期: {purchase_request.get("created_date", "N/A")}
        """

    def _format_purchase_history(self, purchase_history: List[Dict]) -> str:
        """格式化採購歷史資料"""
        if not purchase_history:
            return "沒有相關的採購歷史資料。"

        history_text = ""
        for item in purchase_history:
            history_text += f"""
產品: {item.get("product_name", "N/A")}
類別: {item.get("category", "N/A")}
供應商: {item.get("supplier", "N/A")}
數量: {item.get("quantity", "N/A")}
單價: NT$ {item.get("unit_price", "N/A"):,}
購買日期: {item.get("purchase_date", "N/A")}
狀態: {item.get("status", "N/A")}
---
            """
        return history_text

    def _format_inventory_data(self, inventory_data: List[Dict]) -> str:
        """格式化庫存資料"""
        if not inventory_data:
            return "沒有相關的庫存資料。"

        inventory_text = ""
        for item in inventory_data:
            inventory_text += f"""
產品: {item.get("product_name", "N/A")}
類別: {item.get("category", "N/A")}
目前庫存: {item.get("current_stock", 0)}
可用庫存: {item.get("available_stock", 0)}
預留庫存: {item.get("reserved_stock", 0)}
最低庫存: {item.get("min_stock_level", 0)}
最高庫存: {item.get("max_stock_level", 0)}
成本: NT$ {item.get("unit_cost", 0):,}
位置: {item.get("location", "N/A")}
更新日期: {item.get("last_updated", "N/A")}
---
            """
        return inventory_text

    def chat(self, user_input: str, session_id: str = "default") -> str:
        """主要的對話處理方法"""
        try:
            # 記錄採購專員輸入
            self._add_to_chat_history(session_id, "user", user_input)

            # 智能檢測請購單號 - 優先處理
            request_id = self._extract_request_id(user_input)
            if request_id:
                # 如果輸入中包含請購單號，直接進入分析流程
                return self._handle_analyze_purchase_decision(user_input, session_id)

            # 分類採購專員意圖
            intent_result = self._classify_intent(user_input, session_id)

            # 根據意圖和狀態處理
            if not intent_result.get("is_procurement_related", True):
                response = self._handle_off_topic(user_input, session_id)
            else:
                state = self._get_session_state(session_id)
                current_state = state["conversation_state"]

                if (
                    intent_result.get("intent") == "review_requests"
                    or current_state == ConversationState.INITIAL
                ):
                    response = self._handle_review_requests(user_input, session_id)
                elif (
                    intent_result.get("intent") == "analyze_purchase_decision"
                    or current_state == ConversationState.REVIEWING_REQUESTS
                ):
                    response = self._handle_analyze_purchase_decision(
                        user_input, session_id
                    )
                elif (
                    intent_result.get("intent") == "create_purchase_order"
                    or current_state == ConversationState.ANALYZING_PURCHASE_DECISION
                ):
                    response = self._handle_create_purchase_order(
                        user_input, session_id
                    )
                elif current_state == ConversationState.CREATING_PURCHASE_ORDER:
                    response = self._handle_confirm_purchase_order(
                        user_input, session_id
                    )
                elif current_state == ConversationState.PURCHASE_ORDER_COMPLETED:
                    # 重新開始新的審核流程
                    self._update_session_state(
                        session_id,
                        {
                            "conversation_state": ConversationState.INITIAL,
                            "current_request": None,
                            "decision_analysis": None,
                            "purchase_order": None,
                        },
                    )
                    response = self._handle_review_requests(user_input, session_id)
                else:
                    response = "請告訴我您想要審核哪個請購單？您可以輸入「查看請購單」來查看所有待審核的請購單。"

            # 記錄系統回應
            self._add_to_chat_history(session_id, "assistant", response)

            return response

        except Exception as e:
            logger.error(f"對話處理失敗: {e}")
            return (
                f"抱歉，處理您的訊息時發生錯誤：{str(e)}\n請重新輸入或聯絡系統管理員。"
            )

    def get_session_status(self, session_id: str = "default") -> Dict:
        """獲取會話狀態資訊"""
        return self._get_session_state(session_id)

    def reset_session(self, session_id: str = "default"):
        """重置會話狀態"""
        if session_id in self._session_states:
            del self._session_states[session_id]
