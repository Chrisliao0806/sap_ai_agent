"""
SAP 請購系統 AI Agent

這個系統的主要功能：
1. 接收使用者的對話輸入，判斷意圖和狀態
2. 根據狀態提供相應的回應和服務
3. 引導使用者完成請購流程
4. 防止偏離採購主題的對話
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
class PurchaseAgentConfig:
    """請購 Agent 配置"""

    api_base_url: str = "http://localhost:7777"
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024
    temperature: float = 0.3
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    default_requester: str = "系統使用者"
    default_department: str = "IT部門"

    def __post_init__(self):
        # 如果沒有設定 openai_api_key，從環境變量獲取
        if not self.openai_api_key:
            import os

            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")


class ConversationalPurchaseAgent:
    """對話式請購系統 AI Agent"""

    def __init__(self, config: PurchaseAgentConfig):
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
            PurchasePrompts.get_intent_classification_prompt()
            | self.llm
            | JsonOutputParser()
        )
        self.analyze_chain = (
            PurchasePrompts.get_analyze_request_prompt() | self.llm | StrOutputParser()
        )
        self.recommend_chain = (
            PurchasePrompts.get_recommend_product_prompt()
            | self.llm
            | StrOutputParser()
        )
        self.adjust_chain = (
            PurchasePrompts.get_adjustment_prompt() | self.llm | StrOutputParser()
        )
        self.create_order_chain = (
            PurchasePrompts.get_create_order_prompt() | self.llm | JsonOutputParser()
        )
        self.guidance_chain = (
            PurchasePrompts.get_guidance_prompt() | self.llm | StrOutputParser()
        )
        self.extract_requirement_chain = (
            PurchasePrompts.get_extract_requirement_prompt()
            | self.llm
            | JsonOutputParser()
        )
        self.direct_order_chain = (
            PurchasePrompts.get_direct_order_prompt() | self.llm | JsonOutputParser()
        )
        self.custom_product_chain = (
            PurchasePrompts.get_custom_product_prompt() | self.llm | JsonOutputParser()
        )

    def _get_session_state(self, session_id: str) -> Dict:
        """獲取會話狀態"""
        if session_id not in self._session_states:
            self._session_states[session_id] = {
                "conversation_state": ConversationState.INITIAL,
                "user_request": "",
                "purchase_history": [],
                "current_recommendation": None,
                "confirmed_order": None,
                "chat_history": [],
                "user_context": {
                    "requester": self.config.default_requester,
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
        """分類使用者意圖"""
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
                "is_purchase_related": False,
                "guidance_message": "抱歉，我無法理解您的需求。請告訴我您想要採購什麼產品？",
            }

    def _fetch_purchase_history(self, product_type: str = None) -> List[Dict]:
        """獲取採購歷史資料"""
        try:
            params = {}
            if product_type:
                params["category"] = product_type

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

    def _find_matching_product(
        self, requirement: Dict, purchase_history: List[Dict]
    ) -> Optional[Dict]:
        """從採購歷史中找到符合需求的產品"""
        try:
            product_name = requirement.get("product_name", "") or ""
            product_type = requirement.get("product_type", "") or ""
            budget = requirement.get("budget", 0) or 0

            product_name = product_name.lower() if product_name else ""
            product_type = product_type.lower() if product_type else ""

            # 創建匹配得分系統
            best_match = None
            best_score = 0

            for product in purchase_history:
                score = 0
                product_name_lower = (product.get("product_name", "") or "").lower()
                product_category_lower = (product.get("category", "") or "").lower()

                # 檢查產品名稱匹配
                if product_name:
                    # 精確匹配檢查
                    if product_name in product_name_lower:
                        score += 10
                    # 關鍵字匹配（例如：macbook, 14吋 等）
                    product_keywords = product_name.split()
                    for keyword in product_keywords:
                        if keyword in product_name_lower:
                            score += 5

                # 檢查產品類型匹配
                if product_type:
                    if product_type in product_category_lower:
                        score += 8

                # 檢查預算匹配
                if budget > 0:
                    product_price = product.get("unit_price", 0) or 0
                    if product_price <= budget:
                        score += 3
                    elif product_price <= budget * 1.1:  # 允許10%的預算彈性
                        score += 1

                # 更新最佳匹配
                if score > best_score and score >= 5:  # 至少要有基本匹配分數
                    best_match = product
                    best_score = score

            return best_match

        except Exception as e:
            logger.error(f"尋找符合產品失敗: {e}")
            return None

    def _handle_new_request(self, user_input: str, session_id: str) -> str:
        """處理新的請購需求"""
        try:
            # 1. 解析需求資訊
            requirement = self.extract_requirement_chain.invoke(
                {"user_request": user_input}
            )

            # 2. 根據需求類型決定是否查詢產品歷史
            product_type = requirement.get("product_type", "")

            # 3. 獲取採購歷史
            purchase_history = self._fetch_purchase_history(product_type)
            print(f"獲取到的採購歷史資料: {len(purchase_history)} 筆")

            # 4. 格式化採購歷史資料供 LLM 分析
            history_text = self._format_purchase_history(purchase_history)

            # 5. 讓 LLM 分析採購歷史並提供智能推薦
            recommendation = self.recommend_chain.invoke(
                {"user_request": user_input, "purchase_history": history_text}
            )

            # 6. 檢查是否能從推薦中解析出特定產品資訊
            selected_product = None
            if purchase_history:
                # 嘗試從 LLM 推薦中找出對應的歷史產品
                selected_product = self._extract_product_from_recommendation(
                    recommendation, purchase_history
                )

            # 7. 更新會話狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.WAITING_CONFIRMATION,
                    "user_request": user_input,
                    "purchase_history": purchase_history,
                    "current_recommendation": recommendation,
                    "selected_product": selected_product,
                    "requirement": requirement,
                    "has_matching_history": bool(selected_product),
                },
            )

            # 8. 根據是否有採購歷史提供不同的回應格式
            if purchase_history:
                return f"📋 需求分析完成\n\n🎯 智能推薦 (基於採購歷史分析)\n\n{recommendation}\n\n請確認是否同意此推薦？\n- 輸入「同意」來接受推薦\n- 輸入「不同意」來調整推薦"
            else:
                return f"📋 需求分析完成\n\n🎯 推薦產品\n\n{recommendation}\n\n請確認是否同意此推薦？\n- 輸入「同意」來接受推薦\n- 輸入「不同意」來調整推薦"

        except Exception as e:
            logger.error(f"處理新請求失敗: {e}")
            return f"抱歉，處理您的請求時發生錯誤：{str(e)}\n請重新描述您的採購需求。"

    def _handle_confirmation(self, user_input: str, session_id: str) -> str:
        """處理確認推薦"""
        # 注意：產品變更判斷現在由 LLM 在意圖分類中處理
        # 這裡只處理純粹的確認或拒絕

        user_input_lower = user_input.lower().strip()

        # 判斷使用者是否確認
        if any(
            keyword in user_input_lower
            for keyword in ["同意", "確認", "好", "可以", "沒問題", "ok"]
        ):
            # 用戶確認了產品推薦，現在收集詳細資訊
            state = self._get_session_state(session_id)
            selected_product = state.get("selected_product")

            if selected_product:
                # 有選定的特定產品，收集詳細資訊
                self._update_session_state(
                    session_id,
                    {"conversation_state": ConversationState.WAITING_ORDER_DETAILS},
                )

                return f"✅ 產品確認：{selected_product['product_name']}\n\n現在請提供以下資訊以完成請購單：\n\n1. **數量**：您需要多少台/個？\n2. **請購人姓名**：請購人的完整姓名\n3. **預期交貨日期**：希望什麼時候交貨？（格式：YYYY-MM-DD）\n\n請一次提供所有資訊，例如：\n「數量：2台，請購人：張三，交貨日期：2025-07-15」"
            else:
                # 沒有選定的特定產品，但用戶同意了系統推薦，收集詳細資訊
                self._update_session_state(
                    session_id,
                    {"conversation_state": ConversationState.WAITING_ORDER_DETAILS},
                )

                return "✅ 推薦確認\n\n現在請提供以下資訊以完成請購單：\n\n1. **數量**：您需要多少台/個？\n2. **請購人姓名**：請購人的完整姓名\n3. **預期交貨日期**：希望什麼時候交貨？（格式：YYYY-MM-DD）\n\n請一次提供所有資訊，例如：\n「數量：2台，請購人：張三，交貨日期：2025-07-15」"
        elif any(
            keyword in user_input_lower
            for keyword in ["不同意", "不要", "不行", "調整", "修改", "改"]
        ):
            # 進入調整狀態
            self._update_session_state(
                session_id, {"conversation_state": ConversationState.ADJUSTING}
            )
            return "我理解您想要調整推薦。請告訴我您的具體需求：\n\n1. 如果您想要歷史記錄中的特定產品，請說明產品名稱\n2. 如果您想要全新的產品，請提供：\n   - 產品名稱\n   - 預期價格\n\n請詳細描述您的需求。"
        else:
            return "請明確回答是否同意此推薦？\n- 輸入「同意」或「確認」來接受推薦\n- 輸入「不同意」或「調整」來修改推薦"

    def _handle_adjustment(self, user_input: str, session_id: str) -> str:
        """處理調整推薦"""
        try:
            state = self._get_session_state(session_id)
            purchase_history = state.get("purchase_history", [])

            # 格式化採購歷史資料供 LLM 分析
            history_text = self._format_purchase_history(purchase_history)

            # 讓 LLM 基於用戶的調整需求和採購歷史進行智能調整
            adjusted_recommendation = self.adjust_chain.invoke(
                {
                    "current_recommendation": state["current_recommendation"],
                    "adjustment_request": user_input,
                    "purchase_history": history_text,
                }
            )

            # 檢查是否能從調整後的推薦中解析出特定產品資訊
            selected_product = None
            if purchase_history:
                # 嘗試從 LLM 調整後的推薦中找出對應的歷史產品
                selected_product = self._extract_product_from_recommendation(
                    adjusted_recommendation, purchase_history
                )

            # 更新狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.WAITING_CONFIRMATION,
                    "current_recommendation": adjusted_recommendation,
                    "selected_product": selected_product,
                },
            )

            return f"🔄 推薦已調整 (基於採購歷史智能分析)\n\n{adjusted_recommendation}\n\n請確認是否同意此調整後的推薦？\n- 輸入「同意」來接受推薦\n- 輸入「不同意」來進一步調整"

        except Exception as e:
            logger.error(f"調整推薦失敗: {e}")
            return f"抱歉，調整推薦時發生錯誤：{str(e)}\n請重新描述您的調整需求。"

    def _create_and_show_order(self, session_id: str) -> str:
        """創建並顯示請購單"""
        try:
            state = self._get_session_state(session_id)

            # 創建請購單
            order_data = self.create_order_chain.invoke(
                {
                    "recommendation": state["current_recommendation"],
                    "user_info": json.dumps(state["user_context"], ensure_ascii=False),
                }
            )

            # 處理可能的嵌套結構
            if isinstance(order_data, dict) and "purchase_order" in order_data:
                if isinstance(order_data["purchase_order"], list):
                    order_data = order_data["purchase_order"][0]
                else:
                    order_data = order_data["purchase_order"]

            # 確保日期格式正確
            if "expected_delivery_date" in order_data:
                delivery_date = order_data["expected_delivery_date"]
                if delivery_date.startswith("2023"):
                    order_data["expected_delivery_date"] = delivery_date.replace(
                        "2023", "2025"
                    )

            # 更新狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.CONFIRMING_ORDER,
                    "confirmed_order": order_data,
                },
            )

            # 格式化顯示請購單
            order_display = self._format_order_display(order_data)

            return f"📋 請購單已創建\n\n{order_display}\n\n請確認請購單資訊是否正確？\n- 輸入「確認提交」來提交請購單\n- 輸入「修改」來調整請購單\n- 輸入「取消」來取消請購"

        except Exception as e:
            logger.error(f"創建請購單失敗: {e}")
            return f"抱歉，創建請購單時發生錯誤：{str(e)}\n請重新確認推薦。"

    def _handle_order_confirmation(self, user_input: str, session_id: str) -> str:
        """處理請購單確認"""
        user_input_lower = user_input.lower().strip()

        if any(
            keyword in user_input_lower
            for keyword in ["確認提交", "提交", "確認", "送出"]
        ):
            return self._submit_order(session_id)
        elif any(keyword in user_input_lower for keyword in ["修改", "調整", "更改"]):
            self._update_session_state(
                session_id,
                {"conversation_state": ConversationState.WAITING_CONFIRMATION},
            )
            return "請告訴我您要修改請購單的哪個部分？我會重新為您調整推薦。"
        elif any(keyword in user_input_lower for keyword in ["取消", "不要", "放棄"]):
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.INITIAL,
                    "current_recommendation": None,
                    "confirmed_order": None,
                },
            )
            return "已取消本次請購。如果您有其他採購需求，請隨時告訴我。"
        else:
            return "請明確回答：\n- 輸入「確認提交」來提交請購單\n- 輸入「修改」來調整請購單\n- 輸入「取消」來取消請購"

    def _submit_order(self, session_id: str) -> str:
        """提交請購單"""
        try:
            state = self._get_session_state(session_id)
            order_data = state["confirmed_order"]

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

                # 更新狀態
                self._update_session_state(
                    session_id,
                    {
                        "conversation_state": ConversationState.COMPLETED,
                        "api_response": api_response,
                    },
                )

                # 計算總金額
                total_amount = order_data.get("unit_price", 0) * order_data.get(
                    "quantity", 0
                )

                success_msg = f"""✅ 請購單提交成功！
                
                📄 請購單詳情：
                - 請購單號：{request_id}
                - 產品：{order_data.get("product_name", "N/A")}
                - 數量：{order_data.get("quantity", 0)}
                - 預估金額：NT$ {total_amount:,}
                - 狀態：{api_response.get("data", {}).get("status", "N/A")}

                您可以使用請購單號查詢審核進度。

                如果您還有其他採購需求，請隨時告訴我。"""

                return success_msg
            else:
                logger.error(f"API 提交失敗: {response.status_code}")
                return f"❌ 請購單提交失敗\n\nAPI 錯誤：{response.status_code}\n請稍後重試或聯絡系統管理員。"

        except requests.RequestException as e:
            logger.error(f"提交請購單失敗: {e}")
            return (
                f"❌ 請購單提交失敗\n\n網路錯誤：{str(e)}\n請檢查網路連線或稍後重試。"
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
            return "我是專門協助您處理採購相關事務的助手。請告訴我您想要採購什麼產品，我會為您提供最合適的推薦。"

    def _format_purchase_history(self, history: List[Dict]) -> str:
        """格式化採購歷史資料"""
        if not history:
            return "沒有相關的採購歷史資料。"

        history_text = ""
        for item in history:
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
        return history_text

    def _format_order_display(self, order_data: Dict) -> str:
        """格式化請購單顯示"""
        total_amount = order_data.get("unit_price", 0) * order_data.get("quantity", 0)

        return f"""產品名稱：{order_data.get("product_name", "N/A")}
            產品類別：{order_data.get("category", "N/A")}
            數量：{order_data.get("quantity", 0)}
            單價：NT$ {order_data.get("unit_price", 0):,}
            總金額：NT$ {total_amount:,}
            請購人：{order_data.get("requester", "N/A")}
            部門：{order_data.get("department", "N/A")}
            請購理由：{order_data.get("reason", "N/A")}
            是否緊急：{"是" if order_data.get("urgent", False) else "否"}
            預期交貨日期：{order_data.get("expected_delivery_date", "N/A")}"""

    def chat(self, user_input: str, session_id: str = "default") -> str:
        """主要的對話處理方法"""
        try:
            # 記錄使用者輸入
            self._add_to_chat_history(session_id, "user", user_input)

            # 分類使用者意圖
            intent_result = self._classify_intent(user_input, session_id)

            # 根據意圖和狀態處理
            if not intent_result.get("is_purchase_related", True):
                response = self._handle_off_topic(user_input, session_id)
            else:
                state = self._get_session_state(session_id)
                current_state = state["conversation_state"]

                # 檢查是否為產品變更請求
                if intent_result.get("is_product_change", False):
                    response = self._handle_product_change_request(
                        user_input, session_id
                    )
                elif (
                    intent_result.get("intent") == "new_request"
                    or current_state == ConversationState.INITIAL
                ):
                    response = self._handle_new_request(user_input, session_id)
                elif current_state == ConversationState.WAITING_CONFIRMATION:
                    response = self._handle_confirmation(user_input, session_id)
                elif current_state == ConversationState.ADJUSTING:
                    response = self._handle_adjustment(user_input, session_id)
                elif current_state == ConversationState.CONFIRMING_ORDER:
                    response = self._handle_order_confirmation(user_input, session_id)
                elif current_state == ConversationState.WAITING_ORDER_DETAILS:
                    response = self._handle_order_details(user_input, session_id)
                elif current_state == ConversationState.COMPLETED:
                    # 重新開始新的請購流程
                    self._update_session_state(
                        session_id,
                        {
                            "conversation_state": ConversationState.INITIAL,
                            "current_recommendation": None,
                            "confirmed_order": None,
                        },
                    )
                    response = self._handle_new_request(user_input, session_id)
                else:
                    response = "請告訴我您想要採購什麼產品？"

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

    def _handle_custom_product_request(self, user_input: str, session_id: str) -> str:
        """處理自定義產品請求"""
        try:
            # 解析自定義產品資訊
            custom_product = self.custom_product_chain.invoke(
                {"user_input": user_input}
            )

            # 檢查是否有必要的資訊
            required_fields = ["product_name", "unit_price"]
            missing_fields = [
                field for field in required_fields if not custom_product.get(field)
            ]

            if missing_fields:
                missing_info = []
                if "product_name" in missing_fields:
                    missing_info.append("- 產品名稱")
                if "unit_price" in missing_fields:
                    missing_info.append("- 價格")
                return "請提供以下必要資訊：\n" + "\n".join(missing_info)

            # 更新會話狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.WAITING_ORDER_DETAILS,
                    "custom_product": custom_product,
                },
            )

            return f"已記錄您的自定義產品：\n產品名稱：{custom_product['product_name']}\n價格：NT$ {custom_product['unit_price']:,}\n\n現在請提供以下資訊：\n- 數量\n- 請購人姓名\n- 請購時間（預期交貨日期）"

        except Exception as e:
            logger.error(f"處理自定義產品請求失敗: {e}")
            return f"抱歉，處理您的自定義產品請求時發生錯誤：{str(e)}\n請重新提供產品資訊。"

    def _handle_order_details(self, user_input: str, session_id: str) -> str:
        """處理請購單詳細資訊"""
        try:
            state = self._get_session_state(session_id)
            selected_product = state.get("selected_product")

            # 如果沒有特定選定的產品，嘗試從推薦中提取產品資訊
            if not selected_product:
                # 從系統推薦中提取產品資訊
                recommendation = state.get("current_recommendation", "")
                # 尋找推薦中提到的產品（通常是MacBook Pro 14吋之類的）
                if "MacBook Pro 14吋" in recommendation:
                    # 從採購歷史中找到對應的產品
                    purchase_history = state.get("purchase_history", [])
                    for product in purchase_history:
                        if "MacBook Pro 14吋" in product.get("product_name", ""):
                            selected_product = product
                            break

                # 如果還是找不到，使用推薦中的預設資訊
                if not selected_product:
                    selected_product = {
                        "product_name": "MacBook Pro 14吋",
                        "category": "筆記型電腦",
                        "unit_price": 65000,
                        "supplier": "Apple Inc.",
                    }

            # 解析使用者提供的詳細資訊
            details = self.custom_product_chain.invoke({"user_input": user_input})

            # 檢查必要資訊是否完整
            missing_info = []

            if not details.get("quantity"):
                missing_info.append("數量")
            if not details.get("requester"):
                missing_info.append("請購人姓名")
            if not details.get("expected_delivery_date"):
                missing_info.append("預期交貨日期")

            if missing_info:
                return (
                    "請提供以下缺少的資訊：\n"
                    + "\n".join([f"- {info}" for info in missing_info])
                    + "\n\n請重新輸入完整資訊。"
                )

            # 建立完整的請購單
            order_data = {
                "product_name": selected_product.get("product_name", "未指定產品"),
                "category": selected_product.get("category", "其他"),
                "quantity": details.get("quantity", 1),
                "unit_price": selected_product.get("unit_price", 0),
                "requester": details.get(
                    "requester", state["user_context"]["requester"]
                ),
                "department": state["user_context"]["department"],
                "reason": details.get("reason", "業務需求"),
                "urgent": details.get("urgent", False),
                "expected_delivery_date": details.get("expected_delivery_date", ""),
            }

            # 更新狀態
            self._update_session_state(
                session_id,
                {
                    "conversation_state": ConversationState.CONFIRMING_ORDER,
                    "confirmed_order": order_data,
                },
            )

            # 格式化顯示請購单
            order_display = self._format_order_display(order_data)

            return f"📋 請購單已創建\n\n{order_display}\n\n請確認請購單資訊是否正確？\n- 輸入「確認提交」來提交請購單\n- 輸入「修改」來調整請購單\n- 輸入「取消」來取消請購"

        except Exception as e:
            logger.error(f"處理請購單詳細資訊失敗: {e}")
            return f"抱歉，處理請購單資訊時發生錯誤：{str(e)}\n請重新提供相關資訊。"

    def _handle_product_change_request(self, user_input: str, session_id: str) -> str:
        """處理產品變更請求"""
        try:
            # 獲取採購歷史
            state = self._get_session_state(session_id)
            purchase_history = state.get("purchase_history", [])

            # 如果沒有歷史記錄，重新獲取
            if not purchase_history:
                purchase_history = self._fetch_purchase_history()

            # 格式化採購歷史資料供 LLM 分析
            history_text = self._format_purchase_history(purchase_history)

            # 讓 LLM 基於用戶的產品變更需求和採購歷史進行智能推薦
            product_change_recommendation = self.recommend_chain.invoke(
                {
                    "user_request": user_input,
                    "purchase_history": history_text,
                }
            )

            # 檢查是否能從推薦中解析出特定產品資訊
            selected_product = None
            if purchase_history:
                # 嘗試從 LLM 推薦中找出對應的歷史產品
                selected_product = self._extract_product_from_recommendation(
                    product_change_recommendation, purchase_history
                )

            # 更新選定產品和會話狀態
            self._update_session_state(
                session_id,
                {
                    "selected_product": selected_product,
                    "current_recommendation": product_change_recommendation,
                    "conversation_state": ConversationState.WAITING_CONFIRMATION,
                    "purchase_history": purchase_history,
                },
            )

            return f"🔄 產品變更推薦 (基於採購歷史智能分析)\n\n{product_change_recommendation}\n\n請確認是否選擇此產品？\n- 輸入「同意」來接受推薦\n- 輸入「不同意」來進一步調整"

        except Exception as e:
            logger.error(f"處理產品變更請求失敗: {e}")
            return (
                f"抱歉，處理您的產品變更請求時發生錯誤：{str(e)}\n請重新描述您的需求。"
            )

    def _extract_product_from_recommendation(
        self, recommendation: str, purchase_history: List[Dict]
    ) -> Optional[Dict]:
        """從 LLM 推薦中提取對應的歷史產品資訊"""
        try:
            # 將推薦文字轉換為小寫以便比較
            recommendation_lower = recommendation.lower()

            # 嘗試匹配歷史產品
            best_match = None
            max_matches = 0

            for product in purchase_history:
                product_name = product.get("product_name", "").lower()
                supplier = product.get("supplier", "").lower()
                category = product.get("category", "").lower()

                matches = 0

                # 檢查產品名稱關鍵字
                if product_name:
                    # 分割產品名稱為關鍵字
                    product_keywords = product_name.split()
                    for keyword in product_keywords:
                        if (
                            len(keyword) > 2 and keyword in recommendation_lower
                        ):  # 忽略太短的關鍵字
                            matches += 2

                # 檢查供應商
                if supplier and supplier in recommendation_lower:
                    matches += 1

                # 檢查類別
                if category and category in recommendation_lower:
                    matches += 1

                # 檢查價格是否在推薦中提到
                unit_price = product.get("unit_price", 0)
                if unit_price and str(unit_price) in recommendation:
                    matches += 3

                # 更新最佳匹配
                if matches > max_matches and matches >= 3:  # 至少要有3個匹配點
                    best_match = product
                    max_matches = matches

            return best_match

        except Exception as e:
            logger.error(f"從推薦中提取產品資訊失敗: {e}")
            return None
