from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 泛用 Firestore Document Schemas
# ---------------------------------------------------------------------------

class DocumentCreate(BaseModel):
    """
    建立文件請求資料結構。
    doc_id 為選填，未提供時 Firestore 將自動生成 UUID/DocID。
    """
    doc_id: Optional[str] = Field(None, description="自訂文件 ID (選填，未傳遞時自動生成)")
    data: Dict[str, Any] = Field(..., description="要儲存至 Firestore 文件的 JSON 鍵值對資料")


class DocumentUpdate(BaseModel):
    """
    更新文件請求資料結構。
    """
    data: Dict[str, Any] = Field(..., description="要更新至 Firestore 文件的欄位資料")
    merge: bool = Field(True, description="True 為增量更新 (Merge)，False 為完全覆蓋 (Overwrite)")


class DocumentResponse(BaseModel):
    """
    單一文件回應結構。
    """
    id: str = Field(..., description="Firestore 文件 ID")
    collection: str = Field(..., description="所屬 Collection 名稱")
    data: Dict[str, Any] = Field(..., description="文件內容")


class DocumentListResponse(BaseModel):
    """
    文件清單回應結構。
    """
    collection: str = Field(..., description="Collection 名稱")
    count: int = Field(..., description="取得文件數量")
    documents: List[DocumentResponse] = Field(default_factory=list, description="文件列表")


# ---------------------------------------------------------------------------
# 專屬 Firebase 訂單 (Order) Schemas
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    """
    新增 Firebase 訂單資料結構。
    """
    OrderID: int = Field(..., description="訂單編號")
    CustomerID: int = Field(..., description="顧客編號")
    OrderDate: str = Field(..., description="訂單日期")
    ProductID: int = Field(..., description="產品編號")
    Quantity: int = Field(..., description="購買數量")
    Discount: float = Field(..., description="折扣金額/比例")
    PaymentMethod: str = Field(..., description="付款方式")
    Status: str = Field(..., description="訂單狀態")
    Age: int = Field(..., description="顧客年齡")
    City: str = Field(..., description="居住城市")
    SignupDate: str = Field(..., description="註冊日期")
    CustomerSegment: str = Field(..., description="顧客分群")
    ProductName: str = Field(..., description="產品名稱")
    Category: str = Field(..., description="產品分類")
    UnitPrice: float = Field(..., description="單價")
    Sales: float = Field(..., description="銷售金額")
    OrderValue: float = Field(..., description="訂單總價值")
    NewOrderID: Optional[str] = Field(None, description="新訂單識別碼 (選填，若未填寫則自動帶入生成的 doc_id)")
    PhoneNumber: str = Field(..., description="電話號碼")


class OrderUpdate(BaseModel):
    """
    更新 Firebase 訂單資料結構 (所有欄位皆可選)。
    """
    OrderID: Optional[int] = None
    CustomerID: Optional[int] = None
    OrderDate: Optional[str] = None
    ProductID: Optional[int] = None
    Quantity: Optional[int] = None
    Discount: Optional[float] = None
    PaymentMethod: Optional[str] = None
    Status: Optional[str] = None
    Age: Optional[str] = None
    City: Optional[str] = None
    SignupDate: Optional[str] = None
    CustomerSegment: Optional[str] = None
    ProductName: Optional[str] = None
    Category: Optional[str] = None
    UnitPrice: Optional[float] = None
    Sales: Optional[float] = None
    OrderValue: Optional[float] = None
    NewOrderID: Optional[str] = None
    PhoneNumber: Optional[str] = None


class OrderResponse(OrderCreate):
    """
    訂單單筆回應結構，繼承 OrderCreate 並包含 Firestore 文件 ID。
    """
    id: str = Field(..., description="Firestore 文件 ID")


class OrderListResponse(BaseModel):
    """
    訂單列表回應結構。
    """
    count: int = Field(..., description="取得訂單總筆數")
    orders: List[OrderResponse] = Field(default_factory=list, description="訂單列表")


# ---------------------------------------------------------------------------
# 專屬 Firebase 產品 (Product) Schemas
# ---------------------------------------------------------------------------

class ProductCreate(BaseModel):
    """
    新增 Firebase 產品資料結構 (所有欄位皆為字串)。
    """
    ProductID: str = Field(..., description="產品 ID")
    ProductNameZH: str = Field(..., description="中文品名")
    ProductNameEN: str = Field(..., description="英文品名")
    Category: str = Field(..., description="分類")
    Description: str = Field(..., description="產品詳細說明")
    DescriptionShort: str = Field(..., description="產品簡短說明 (25字內)")


class ProductUpdate(BaseModel):
    """
    更新 Firebase 產品資料結構 (所有欄位皆可選)。
    """
    ProductID: Optional[str] = None
    ProductNameZH: Optional[str] = None
    ProductNameEN: Optional[str] = None
    Category: Optional[str] = None
    Description: Optional[str] = None
    DescriptionShort: Optional[str] = None


class ProductResponse(ProductCreate):
    """
    產品單筆回應結構。
    """
    id: str = Field(..., description="Firestore 文件 ID")


class ProductListResponse(BaseModel):
    """
    產品列表回應結構 (支援分頁)。
    """
    pidx: int = Field(..., description="當前頁碼 (1-based)")
    pno: int = Field(..., description="每頁筆數")
    count: int = Field(..., description="本頁回傳筆數")
    products: List[ProductResponse] = Field(default_factory=list, description="產品列表")


# ---------------------------------------------------------------------------
# 系統與健康檢查 Schemas
# ---------------------------------------------------------------------------

class HealthStatus(BaseModel):
    """
    健康檢查回應結構。
    """
    status: str = Field(..., description="服務狀態 ('healthy' 或 'degraded')")
    app_name: str = Field(..., description="應用程式名稱")
    firebase_connected: bool = Field(..., description="Firebase Firestore 連線狀態")
    details: Optional[str] = Field(None, description="詳細狀態或警告說明")


class ErrorDetail(BaseModel):
    """
    錯誤詳細資訊結構。
    """
    detail: str = Field(..., description="錯誤訊息說明")
