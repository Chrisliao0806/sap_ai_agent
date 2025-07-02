from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class State(TypedDict):
    """SAP Agent 的狀態定義"""

    question: str
    formatted_question: str
    documents: List[str]
    generation: str
    chat_history: List[Dict[str, str]]
    api_data: Optional[Dict[str, Any]]
    agent_type: str
    # 新增請購單狀態管理
    purchase_request_state: Optional[
        str
    ]  # "collecting_info", "ready_to_create", "creating", "completed"
    pending_purchase_data: Optional[Dict[str, Any]]  # 待創建的請購單資料


class PurchaseHistoryState(BaseModel):
    """
    採購歷史查詢工具。當使用者詢問採購記錄、採購歷史、過去的採購等相關問題時使用。
    """

    query: str = Field(description="使用採購歷史查詢工具時輸入的問題")


class InventoryState(BaseModel):
    """
    庫存查詢工具。當使用者詢問庫存、存貨、商品數量、低庫存等相關問題時使用。
    """

    query: str = Field(description="使用庫存查詢工具時輸入的問題")


class PurchaseRequestState(BaseModel):
    """
    請購單工具。當使用者要創建請購單、查詢請購單狀態、審核進度等相關問題時使用。
    """

    query: str = Field(description="使用請購單工具時輸入的問題")


class GeneralChatState(BaseModel):
    """
    一般聊天工具。當問題與採購、庫存、請購單都無關時，使用一般聊天功能。
    """

    query: str = Field(description="使用一般聊天時輸入的問題")


class CreatePurchaseRequestData(BaseModel):
    """創建請購單的資料結構"""

    product_name: str = Field(description="產品名稱")
    category: str = Field(description="產品類別", default="3C產品")
    quantity: int = Field(description="數量")
    unit_price: float = Field(description="單價")
    requester: str = Field(description="申請人")
    department: str = Field(description="部門")
    reason: str = Field(description="申請原因", default="")
    urgent: bool = Field(description="是否緊急", default=False)
    expected_delivery_date: str = Field(description="預期交付日期", default="")
