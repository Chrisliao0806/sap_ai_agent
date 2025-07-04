"""
SAP 請購系統 AI Agent - 狀態和資料結構

包含所有的 TypedDict 狀態定義和 Pydantic 模型
"""

from typing import Dict, List
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class PurchaseRequestState(TypedDict):
    """請購狀態定義"""

    user_request: str  # 使用者請購需求
    purchase_history: List[Dict]  # 採購歷史資料
    recommendations: str  # LLM 推薦結果
    user_approval: bool  # 使用者是否同意推薦
    purchase_order: Dict  # 請購單資料
    api_response: Dict  # API 回應
    chat_history: List[Dict]  # 對話歷史
    current_step: str  # 目前步驟


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