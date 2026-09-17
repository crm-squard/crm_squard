"""FastAPI 請求/回應格式。前端依 type 欄位決定要 render 哪一種訊息元件。"""
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    # assistant 回答上限比使用者訊息寬鬆：max_new_tokens=512 的生成結果換算中文字數可能超過 500，
    # 這裡限制的是「回傳的歷史紀錄」本身，不是使用者新輸入（那個仍受 ChatRequest.message 500 字限制）。
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    # 上限 500 字：避免超長輸入把 LLM context 塞爆或拖慢生成速度
    message: str = Field(min_length=1, max_length=500)
    # 前端傳回目前對話中「之前幾輪」的訊息，用來讓機器人記得上下文（例如「那電池呢？」）。
    # 只有產品問答（type == "product"）這條路徑會用到；訂單查詢是規則比對，不需要歷史。
    history: List[HistoryTurn] = Field(default_factory=list, max_length=20)
    # 要用哪個 LLM 回答；local 是本地 Qwen3.5-2B（僅限 Apple Silicon 開發機），
    # 其餘是線上付費 API（見 app/providers.py）
    provider: Literal["local", "anthropic", "openai", "google", "xai"] = "google"


class SourceRef(BaseModel):
    text: str
    source: str
    topic: str = ""
    distance: float


class ChatResponse(BaseModel):
    type: str  # "product" | "order" | "text"

    # type == "product" | "text"
    text: Optional[str] = None
    source: Optional[str] = None
    sources: Optional[List[SourceRef]] = None

    # type == "order"
    code: Optional[str] = None
    status: Optional[int] = None
    eta: Optional[str] = None
    items: Optional[str] = None


class DailySummaryResponse(BaseModel):
    date: str
    question_count: int
    summary: str


class ProviderInfo(BaseModel):
    id: str
    label: str
    configured: bool


class WidgetTheme(BaseModel):
    primary_color: str = Field(serialization_alias="primaryColor", pattern=r"^#[0-9a-fA-F]{6}$")
    surface_color: str = Field(serialization_alias="surfaceColor", pattern=r"^#[0-9a-fA-F]{6}$")
    text_color: str = Field(serialization_alias="textColor", pattern=r"^#[0-9a-fA-F]{6}$")
    border_radius: int = Field(serialization_alias="borderRadius", ge=0, le=32)


class WidgetConfig(BaseModel):
    brand_name: str = Field(serialization_alias="brandName", min_length=1, max_length=80)
    welcome_message: str = Field(serialization_alias="welcomeMessage", min_length=1, max_length=500)
    logo_url: Optional[str] = Field(default=None, serialization_alias="logoUrl")
    theme: WidgetTheme
    quick_replies: List[str] = Field(serialization_alias="quickReplies", default_factory=list)


class DocumentInfo(BaseModel):
    # 路徑是純粹給人看/篩選用的顯示欄位，不是身分依據——身分是後端 kb_documents.doc_id
    # （內容的 SHA256 唯一對應），對外 API 完全不會出現這個內部流水號，一律用 path 溝通。
    path: str
    tags: List[str] = Field(default_factory=list)
    chunk_count: int
    # 這次呼叫是否真的重新 embed 過：新增/內容更新固定 True；標籤更新/掛到既有內容
    # （linked）/完全沒變都固定 False。列表查詢（GET）不適用，固定給 None。
    content_changed: Optional[bool] = None
    uploaded_at: Optional[str] = None
    file_size_bytes: Optional[int] = None
    # 伺服器端算出的 SHA256，給前端跟自己算的 client 端雜湊核對用。
    content_hash: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]


class PrecheckItem(BaseModel):
    path: str
    client_sha256: str
    tags: List[str] = Field(default_factory=list)


class PrecheckRequest(BaseModel):
    # 資料夾全量覆蓋模式用：算「這次上傳沒包含到的既有路徑」（見 PrecheckResponse.stale_paths）。
    scope_prefix: Optional[str] = None
    # 上限 200：避免單次預檢請求塞爆，多檔案上傳的前端應自行分批。
    items: List[PrecheckItem] = Field(min_length=1, max_length=200)


class PrecheckResultItem(BaseModel):
    path: str
    # linked：這個內容雜湊命中「別的」既有內容（不管這個路徑本來有沒有紀錄），只需要更新
    # 標籤紀錄指向該內容，不需要重新上傳/重新 embed——取代原本的 duplicate_of／renamed 概念。
    status: Literal["new", "unchanged", "content_changed", "tags_only_changed", "linked"]


class PrecheckResponse(BaseModel):
    items: List[PrecheckResultItem]
    # scope_prefix 底下、這次上傳沒包含到的既有路徑；沒帶 scope_prefix 就固定是空陣列。
    stale_paths: List[str] = Field(default_factory=list)


# ---- 多租戶帳號 / Google 登入 / 公司管理（Phase 1，見 app/auth.py、app/accounts_store.py） ----


class GoogleLoginRequest(BaseModel):
    id_token: str


class AccountInfo(BaseModel):
    id: str
    email: str
    role: Literal["platform_primary", "platform_secondary", "tenant_primary", "tenant_secondary"]
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    # 這個帳號在「某一家公司」的身分（'primary'／'secondary'），只有透過
    # GET /api/admin/accounts?company_id= 查出來的帳號才有值；跟上面的 role（全域角色）
    # 是分開的兩件事，見 accounts_store.list_accounts_for_company() 的說明。
    company_role: Optional[Literal["primary", "secondary"]] = None


class LoginResponse(BaseModel):
    token: str
    account: AccountInfo


class CompanyInfo(BaseModel):
    id: str
    name: str
    mcp_url: Optional[str] = None
    welcome_message: Optional[str] = None
    quick_replies: Optional[List[str]] = None
    created_at: Optional[str] = None
    # 目前登入帳號在這家公司的身分（'primary'／'secondary'），只有 /api/auth/me 對 tenant
    # 角色回傳時才有值；platform 角色沒有「依公司而變」的身分，固定是 None。
    your_role: Optional[Literal["primary", "secondary"]] = None


class MeResponse(BaseModel):
    account: AccountInfo
    companies: List[CompanyInfo]


class CompanyListResponse(BaseModel):
    companies: List[CompanyInfo]


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mcp_url: Optional[str] = Field(default=None, max_length=500)
    welcome_message: Optional[str] = Field(default=None, max_length=500)
    quick_replies: Optional[List[str]] = Field(default=None, max_length=10)


class CompanyUpdateRequest(BaseModel):
    # 只更新有帶值的欄位；沒帶的欄位維持不變（不是清空），見 accounts_store.update_company()。
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    mcp_url: Optional[str] = Field(default=None, max_length=500)
    welcome_message: Optional[str] = Field(default=None, max_length=500)
    quick_replies: Optional[List[str]] = Field(default=None, max_length=10)


class AccountCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["platform_primary", "platform_secondary", "tenant_primary", "tenant_secondary"]
    # tenant_* 角色新增時必填（要綁定到哪家公司）；platform_* 角色不需要。
    company_id: Optional[str] = None


class AccountListResponse(BaseModel):
    accounts: List[AccountInfo]


class AuditLogEntry(BaseModel):
    id: int
    actor_email: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[str] = None
    detail: Optional[Any] = None
    created_at: Optional[str] = None


class AuditLogListResponse(BaseModel):
    entries: List[AuditLogEntry]
