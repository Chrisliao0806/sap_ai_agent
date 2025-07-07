"""
SAP 請購系統 AI Agent - 狀態和資料結構

包含所有的 TypedDict 狀態定義和 Pydantic 模型
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from enum import Enum


class ConversationState(str, Enum):
    """對話狀態枚舉"""

    INITIAL = "initial"  # 初始狀態，等待需求輸入
    ANALYZING = "analyzing"  # 分析需求中
    RECOMMENDING = "recommending"  # 推薦產品中
    WAITING_CONFIRMATION = "waiting_confirmation"  # 等待確認推薦
    ADJUSTING = "adjusting"  # 調整推薦中
    CONFIRMING_ORDER = "confirming_order"  # 確認請購單
    WAITING_ORDER_DETAILS = "waiting_order_details"  # 等待請購單詳細資訊
    SUBMITTING = "submitting"  # 提交請購單
    COMPLETED = "completed"  # 完成
    ERROR = "error"  # 錯誤狀態
    
    # 新增採購專員相關狀態
    REVIEWING_REQUESTS = "reviewing_requests"  # 審核請購單
    ANALYZING_PURCHASE_DECISION = "analyzing_purchase_decision"  # 分析採購決策
    CREATING_PURCHASE_ORDER = "creating_purchase_order"  # 創建採購單
    CONFIRMING_PURCHASE_ORDER = "confirming_purchase_order"  # 確認採購單
    PURCHASE_ORDER_COMPLETED = "purchase_order_completed"  # 採購單完成


class PurchaseRequestState(TypedDict):
    """請購狀態定義"""

    user_request: str  # 使用者請購需求
    conversation_state: ConversationState  # 對話狀態
    purchase_history: List[Dict]  # 採購歷史資料
    current_recommendation: Optional[Dict]  # 當前推薦
    confirmed_order: Optional[Dict]  # 確認的請購單
    api_response: Optional[Dict]  # API 回應
    chat_history: List[Dict]  # 對話歷史
    user_context: Dict  # 使用者上下文資訊
    error_message: Optional[str]  # 錯誤訊息


class PurchaseRecommendation(BaseModel):
    """產品推薦結構"""

    product_name: str = Field(description="推薦的產品名稱")
    category: str = Field(description="產品類別")
    supplier: str = Field(description="建議供應商")
    quantity: int = Field(description="建議數量")
    unit_price: int = Field(description="建議單價")
    total_amount: int = Field(description="總金額")
    reason: str = Field(description="推薦理由")
    alternatives: List[str] = Field(description="替代方案", default=[])


class PurchaseOrder(BaseModel):
    """請購單結構"""

    product_name: str = Field(description="產品名稱")
    category: str = Field(description="產品類別")
    quantity: int = Field(description="數量")
    unit_price: int = Field(description="單價")
    requester: str = Field(description="請購人")
    department: str = Field(description="部門")
    reason: str = Field(description="請購理由")
    urgent: bool = Field(description="是否緊急", default=False)
    expected_delivery_date: str = Field(description="預期交貨日期", default="")
