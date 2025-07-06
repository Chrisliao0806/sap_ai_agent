"""
SAP 請購系統 AI Agent - Prompt 模板

包含所有的 LangChain 提示模板
"""

from langchain_core.prompts import ChatPromptTemplate


class PurchasePrompts:
    """請購系統提示模板集合"""

    @staticmethod
    def get_intent_classification_prompt():
        """意圖分類提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的採購助手。請分析使用者的輸入並判斷其意圖和當前應該的對話狀態。

對話狀態說明：
- new_request: 新的請購需求
- confirm_recommendation: 確認推薦
- request_adjustment: 要求調整
- confirm_order: 確認請購單
- submit_order: 提交請購單
- off_topic: 與採購無關的話題
- unclear: 不清楚的輸入

請根據使用者輸入和當前狀態，判斷使用者的意圖並回傳對應的狀態。
如果使用者偏離採購主題，請禮貌地將話題導回採購相關內容。

請用JSON格式回覆，包含：
- intent: 使用者意圖
- next_state: 下一個對話狀態  
- is_purchase_related: 是否與採購相關（布林值）
- guidance_message: 如果需要引導使用者，提供引導訊息""",
                ),
                (
                    "human",
                    """
當前對話狀態：{current_state}
使用者輸入：{user_input}
對話歷史：{chat_history}

請判斷使用者意圖和下一步狀態。
                """,
                ),
            ]
        )

    @staticmethod
    def get_analyze_request_prompt():
        """需求分析提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的採購需求分析師。請分析使用者的請購需求，並提取關鍵資訊。
            
分析要點：
1. 產品類型和規格需求
2. 數量需求
3. 預算考量
4. 使用用途
5. 時間需求

請用繁體中文回覆，並整理成結構化的分析報告。""",
                ),
                ("human", "使用者請購需求：{user_request}"),
            ]
        )

    @staticmethod
    def get_recommend_product_prompt():
        """產品推薦提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的採購顧問。根據使用者需求和採購歷史資料，推薦最合適的產品規格。
            
分析依據：
1. 採購歷史中的產品規格、價格、供應商表現
2. 使用者的具體需求
3. 成本效益分析
4. 供應商可靠性

請提供具體的產品推薦，包括：
- 產品名稱和規格
- 建議供應商
- 建議數量和單價
- 總金額
- 推薦理由
- 替代方案（如果有）

請用繁體中文回覆，並在最後詢問使用者是否同意此推薦，或是否需要調整。""",
                ),
                (
                    "human",
                    """
使用者需求：{user_request}

採購歷史資料：
{purchase_history}

請提供產品推薦。
                """,
                ),
            ]
        )

    @staticmethod
    def get_adjustment_prompt():
        """調整推薦提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的採購顧問。使用者對當前推薦有調整需求，請根據使用者的反饋調整推薦內容。

請根據使用者的調整要求，修改推薦內容，包括：
- 產品名稱和規格
- 建議供應商
- 建議數量和單價
- 總金額
- 調整理由

請用繁體中文回覆，並再次詢問使用者是否滿意調整後的推薦。""",
                ),
                (
                    "human",
                    """
當前推薦：{current_recommendation}
使用者調整要求：{adjustment_request}
採購歷史參考：{purchase_history}

請提供調整後的推薦。
                """,
                ),
            ]
        )

    @staticmethod
    def get_create_order_prompt():
        """請購單創建提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的請購單助手。根據使用者確認的產品推薦，創建正式的請購單。
            
請購單必須包含以下欄位：
1. product_name - 產品名稱
2. category - 類別
3. quantity - 數量
4. unit_price - 單價（整數）
5. requester - 請購人
6. department - 部門
7. reason - 請購理由
8. urgent - 是否緊急（布林值）
9. expected_delivery_date - 預期交貨日期（格式：YYYY-MM-DD，使用2025年的日期）

重要注意事項：
- 欄位名稱必須完全匹配API要求
- 日期必須是2025年的有效日期
- urgent欄位必須是布林值（true/false）
- unit_price必須是整數

請用 JSON 格式回覆，確保所有欄位名稱正確。""",
                ),
                (
                    "human",
                    """
確認的產品推薦：{recommendation}
使用者資訊：{user_info}

請創建請購單，使用正確的欄位名稱和2025年的日期。
                """,
                ),
            ]
        )

    @staticmethod
    def get_guidance_prompt():
        """引導提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個友善的採購助手。使用者的輸入偏離了採購主題，請禮貌地將話題導回採購相關內容。

請用溫和、友善的方式回應，並提供一些採購相關的引導建議。
使用繁體中文回覆。""",
                ),
                (
                    "human",
                    """
使用者輸入：{user_input}
當前狀態：{current_state}

請提供引導訊息，將話題導回採購相關內容。
                """,
                ),
            ]
        )

    @staticmethod
    def get_extract_requirement_prompt():
        """需求提取提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的需求分析師。請從使用者的請購需求中提取關鍵資訊。
            
請提取以下資訊：
- product_name: 產品名稱（如果明確提及）
- product_type: 產品類型/類別（如：筆記型電腦、手機、平板等）
- budget: 預算（數字，如果提及）
- quantity: 數量（如果提及）
- urgency: 緊急程度
- specifications: 規格需求

請用JSON格式回覆，包含提取到的資訊。如果某個欄位沒有明確提及，則設為null或空字串。""",
                ),
                ("human", "使用者請購需求：{user_request}"),
            ]
        )

    @staticmethod
    def get_direct_order_prompt():
        """直接創建請購單提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的請購單助手。根據使用者需求和匹配的歷史產品，創建正式的請購單。
            
請購單必須包含以下欄位：
1. product_name - 產品名稱
2. category - 類別
3. quantity - 數量（預設為1）
4. unit_price - 單價（整數）
5. requester - 請購人
6. department - 部門
7. reason - 請購理由
8. urgent - 是否緊急（布林值）
9. expected_delivery_date - 預期交貨日期（格式：YYYY-MM-DD，使用2025年的日期）

重要注意事項：
- 基於匹配的歷史產品資訊
- 根據使用者需求調整數量
- 日期必須是2025年的有效日期
- urgent欄位必須是布林值（true/false）
- unit_price必須是整數

請用 JSON 格式回覆，確保所有欄位名稱正確。""",
                ),
                (
                    "human",
                    """
使用者需求：{requirement}
匹配的歷史產品：{matching_product}
使用者資訊：{user_info}

請創建請購單，使用正確的欄位名稱和2025年的日期。
                """,
                ),
            ]
        )

    @staticmethod
    def get_custom_product_prompt():
        """自定義產品提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的產品資訊分析師。請從使用者輸入中提取產品和請購資訊。
            
請提取以下資訊：
- product_name: 產品名稱
- category: 產品類別
- unit_price: 單價（整數）
- quantity: 數量
- requester: 請購人姓名
- reason: 請購理由
- urgent: 是否緊急（布林值）
- expected_delivery_date: 預期交貨日期（格式：YYYY-MM-DD）

請用JSON格式回覆，包含提取到的資訊。如果某個欄位沒有明確提及，則設為null或空字串。""",
                ),
                ("human", "使用者輸入：{user_input}"),
            ]
        )
