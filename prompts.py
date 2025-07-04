"""
SAP 請購系統 AI Agent - Prompt 模板

包含所有的 LangChain 提示模板
"""

from langchain_core.prompts import ChatPromptTemplate


class PurchasePrompts:
    """請購系統提示模板集合"""

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
            - 推薦理由
            - 替代方案
            
            請用繁體中文回覆。""",
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
    def get_create_order_prompt():
        """請購單創建提示"""
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一個專業的請購單助手。根據使用者確認的產品推薦，創建正式的請購單。
            
            請購單必須包含：
            1. 產品名稱
            2. 類別
            3. 數量
            4. 單價
            5. 請購人
            6. 部門
            7. 請購理由
            8. 是否緊急
            9. 預期交貨日期
            
            請用 JSON 格式回覆。""",
                ),
                (
                    "human",
                    """
            產品推薦：{recommendation}
            使用者資訊：{user_info}
            
            請創建請購單。
            """,
                ),
            ]
        )
