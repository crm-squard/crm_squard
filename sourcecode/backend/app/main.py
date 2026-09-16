"""
FastAPI 入口。

單一對話窗設計：前端統一打 /api/chat，後端依訊息內容自動判斷是
「訂單查詢」（#2，比對訂單編號格式）還是「產品問題」（#1，交給 ProductQueryAgent 做 RAG），
對應提案「單一對話框、後端自動判斷」的架構。
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from app import accounts_store, auth
from app.config import settings
from app.schemas import (
    AccountCreateRequest,
    AccountInfo,
    AccountListResponse,
    AuditLogEntry,
    AuditLogListResponse,
    ChatRequest,
    ChatResponse,
    CompanyCreateRequest,
    CompanyInfo,
    CompanyListResponse,
    CompanyUpdateRequest,
    DailySummaryResponse,
    DocumentInfo,
    DocumentListResponse,
    GoogleLoginRequest,
    LoginResponse,
    MeResponse,
    PrecheckRequest,
    PrecheckResponse,
    PrecheckResultItem,
    ProviderInfo,
    WidgetConfig,
    WidgetTheme,
)
from app.agent import get_agent
from app.orders import get_order, init_db as init_orders_db
from app.chat_log import init_db as init_chat_log_db, log_chat
from app.summary import summarize_day
from app.providers import is_configured
from app.line_webhook import create_line_router

PROVIDER_LABELS = {
    "local": "本地 Qwen3.5-2B（免費，僅限 Apple Silicon 開發機）",
    "anthropic": "Claude",
    "openai": "GPT",
    "google": "Gemini",
    "xai": "Grok",
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_CLIENT_ID_LENGTH = 128


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時預載 DB；避免在啟動階段載入重型模型導致 Cloud Run 健康檢查逾時
    try:
        init_chat_log_db()
        init_orders_db()
    except Exception as e:
        print(f"[Warning] Backend startup db init failed: {e}")
    try:
        # 多租戶帳號表（companies/accounts/company_accounts/sessions/audit_log）冪等建立，
        # 順便跑 bootstrap_initial_platform_admins()（見 accounts_store._ensure_schema()）。
        accounts_store._ensure_schema()
    except Exception as e:
        print(f"[Warning] Backend startup accounts_store schema init failed: {e}")
    yield



app = FastAPI(title="智慧CRM系統 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 同時支援兩種訂單編號格式：
# - ORD-500001（corp-backend/Firestore 的真實訂單 ID，ORD- + 6位數字）
# - A12345（1個英文字母 + 5位數字，舊版 SQLite fallback mock 資料用）
# \b 邊界避免誤吃：例如沒有它，A123456 會被截斷誤判成 A12345。
ORDER_CODE_PATTERN = re.compile(r"\bORD-\d{6}\b|\b[A-Za-z]\d{5}\b")

# 簡易 rate limit：同一 IP 每 60 秒最多 RATE_LIMIT_MAX_REQUESTS 次 /api/chat 請求。
# 記憶體版實作，僅適合單一服務程序；多台伺服器水平擴充時需改用 Redis 等共用儲存。
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 20
_request_log: dict[str, deque] = defaultdict(deque)

# company_id（X-Client-ID）額外的限流：company_id 是公開識別碼，會出現在客戶網站的
# widget 原始碼裡，不是密鑰，任何人都拿得到；只靠上面的 per-IP 限流擋不住「換 IP／用多台
# 機器打同一個 company_id」的濫用，所以另外對 company_id 本身也做一組更寬鬆的總量限制
# （一家商家的真實流量本來就會來自很多不同顧客的 IP，門檻要比單一 IP 高很多）。
COMPANY_RATE_LIMIT_WINDOW_SECONDS = 60
COMPANY_RATE_LIMIT_MAX_REQUESTS = 120
_company_request_log: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(client_ip: str):
    now = time.time()
    timestamps = _request_log[client_ip]
    while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="請求過於頻繁，請稍後再試。")
    timestamps.append(now)


def _check_company_rate_limit(company_id: str):
    now = time.time()
    timestamps = _company_request_log[company_id]
    while timestamps and now - timestamps[0] > COMPANY_RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()
    if len(timestamps) >= COMPANY_RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="這家商家的聊天機器人請求量過大，請稍後再試。")
    timestamps.append(now)


def _require_client_id(
    x_client_id: str | None = Header(default=None, alias="X-Client-ID"),
) -> str:
    """先固定企業客戶識別介面；唯一性與啟停狀態由未來客戶管理服務驗證。"""
    client_id = x_client_id.strip() if x_client_id else ""
    if not client_id or len(client_id) > MAX_CLIENT_ID_LENGTH:
        raise HTTPException(status_code=422, detail="X-Client-ID 必填，且長度不得超過 128 個字元。")
    return client_id


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- 多租戶帳號：Google 登入 / session / 目前登入者資訊（Phase 1，見 app/auth.py） ----


@app.post("/api/auth/google", response_model=LoginResponse)
def login_with_google(req: GoogleLoginRequest):
    """
    驗證前端拿到的 Google ID token，查帳號表；帳號不存在時自動建立一個 tenant_primary 帳號
    （商家自助註冊，不用平台方手動加入），但不會自動幫他建立任何企業服務（company），
    商家登入後要自己在後台新增第一個企業服務。驗證成功建立 session，回傳明文 token
    （僅此一次，之後的請求都帶 Authorization: Bearer <token>）。
    """
    try:
        email = auth.verify_google_id_token(req.id_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    account = accounts_store.get_account_by_email(email)
    if account is None:
        try:
            account = accounts_store.create_account(email, "tenant_primary", created_by=None)
        except IntegrityError:
            # 同一個新 email 在極短時間內併發登入兩次，兩者都查到 None 才會撞到這裡；
            # email 欄位有 UNIQUE 限制，其中一次 insert 會失敗，改查已經插入成功的那筆即可。
            account = accounts_store.get_account_by_email(email)
        accounts_store.record_audit(
            account["id"], action="self_register", target_type="account", target_id=account["id"],
            detail={"email": email},
        )
    token = accounts_store.create_session(account["id"])
    return LoginResponse(token=token, account=AccountInfo(**account))


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    """撤銷目前 session（刪掉對應的 sessions row）。沒帶 token 或格式錯誤視同已登出，不報錯。"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()
        if token:
            accounts_store.revoke_session(token)
    return {"status": "logged_out"}


@app.get("/api/auth/me", response_model=MeResponse)
def get_me(account: dict = Depends(auth.require_session)):
    """回傳目前登入帳號資訊，以及這個帳號看得到的公司清單（platform 角色回全部）。"""
    companies = accounts_store.list_companies_visible_to(account)
    return MeResponse(
        account=AccountInfo(**account),
        companies=[CompanyInfo(**c) for c in companies],
    )


@app.post("/api/warmup")
def warmup():
    """手動觸發載入 Embedding / LLM 模型，避免第一次聊天時使用者要空等模型下載。"""
    get_agent()
    return {"status": "models loaded"}


@app.get("/api/providers", response_model=list[ProviderInfo])
def list_providers(_client_id: str = Depends(_require_client_id)):
    """前端聊天視窗用來畫「選擇回答模型」下拉選單，含每個 provider 有沒有設定 key。"""
    return [
        ProviderInfo(id=pid, label=label, configured=is_configured(pid))
        for pid, label in PROVIDER_LABELS.items()
    ]


DEFAULT_WELCOME_MESSAGE = "您好，我是線上客服，可以問我任何產品的規格、特色，或是輸入訂單編號查詢配送狀態喔。"
DEFAULT_QUICK_REPLIES = ["無線滑鼠支援多少 DPI？", "查詢訂單 A12345", "退貨要幾天內申請？"]


@app.get("/api/widget/config", response_model=WidgetConfig)
def widget_config(_client_id: str = Depends(_require_client_id)):
    """
    開頭語（welcome_message）、開場快速提問（quick_replies）依 _client_id（就是
    company_id，見 _lookup_company）讀取公司自訂的值；查無公司或公司沒填就退回
    DEFAULT_WELCOME_MESSAGE／DEFAULT_QUICK_REPLIES（原本 chat-widget 端寫死的內容搬過來
    當預設值），不讓 widget 掛掉。其餘品牌樣式 MVP 先共用，之後可以一併搬進公司資訊頁面。
    """
    company = _lookup_company(_client_id)
    welcome_message = (company.get("welcome_message") if company else None) or DEFAULT_WELCOME_MESSAGE
    quick_replies = (company.get("quick_replies") if company else None) or DEFAULT_QUICK_REPLIES
    return WidgetConfig(
        brand_name="線上客服",
        welcome_message=welcome_message,
        logo_url=None,
        theme=WidgetTheme(
            primary_color="#315b7d",
            surface_color="#ffffff",
            text_color="#17212b",
            border_radius=20,
        ),
        quick_replies=quick_replies,
    )


@app.get("/api/admin/summary", response_model=DailySummaryResponse)
def admin_summary(
    company_id: str = Query(...),
    date: str | None = None,
    _account: dict = Depends(auth.require_company_access),
):
    """
    管理者查看指定公司、指定日期（預設今天，UTC）使用者提問的主題摘要。

    company_id 必填 + require_company_access：只有 platform 帳號或綁定這家公司的帳號
    才能看到這家公司的顧客提問內容，比照 /api/admin/documents* 的驗證模式。
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif not DATE_PATTERN.match(date):
        raise HTTPException(status_code=400, detail="date 格式須為 YYYY-MM-DD")

    try:
        result = summarize_day(date, company_id)
    except Exception as e:
        # 同 /api/chat：未預期的例外要在應用程式層處理掉，回傳正常的錯誤回應，
        # 避免整個請求掛掉變成 Cloud Run 層級的 502/503（不帶 CORS 標頭）。
        print(f"[Summary Error] {e}")
        raise HTTPException(status_code=502, detail="產生摘要時發生錯誤，請稍後再試。")
    return DailySummaryResponse(**result)


def _get_llamaindex_index():
    """文檔管理 API 專用：取得 llamaindex 引擎的 pgvector 索引。"""
    from app.rag.engine import get_retriever

    return get_retriever().index


@app.get("/api/admin/documents", response_model=DocumentListResponse)
def list_documents(company_id: str = Query(...), _account: dict = Depends(auth.require_company_access)):
    """
    列出這家公司知識庫目前所有路徑（一份內容掛兩個路徑就是兩列，各自標籤），供管理頁面畫列表。

    company_id 查詢參數 + require_company_access：只有 platform 帳號或綁定這家公司的帳號
    才能查看（見 app/auth.py）。
    """
    from app.rag.documents_store import list_documents as _list_documents

    _get_llamaindex_index()  # 確認 pgvector 連線正常，不通就提早回錯誤
    try:
        docs = _list_documents(company_id)
    except Exception as e:
        print(f"[Documents Error] list failed: {e}")
        raise HTTPException(status_code=502, detail="讀取知識庫文件列表時發生錯誤，請稍後再試。")
    return DocumentListResponse(documents=[DocumentInfo(**d) for d in docs])


def _read_md_upload(file: UploadFile) -> str:
    """驗證上傳檔案是 .md，讀成文字。目前只支援純文字 markdown，其他格式一律拒絕。"""
    if not file.filename or not file.filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="目前只支援 .md 檔案。")
    raw_bytes = file.file.read()
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="檔案編碼須為 UTF-8。")


def _check_client_hash(server_hash: str, client_sha256: str):
    """
    硬性檢查：上傳前端算的雜湊要跟伺服器重算的一致，才允許寫入。避免瀏覽器讀檔/傳輸過程
    內容跟預檢（precheck）階段比對的內容不一致（例如使用者在預檢後又動了檔案），
    這個檢查故意設計成擋下請求，不只是回傳給前端自行比對。
    """
    if server_hash != client_sha256:
        raise HTTPException(status_code=400, detail="檔案內容與上傳前計算的雜湊不符，請重新選檔上傳。")


@app.post("/api/admin/documents/precheck", response_model=PrecheckResponse)
def precheck_documents(
    req: PrecheckRequest, company_id: str = Query(...), _account: dict = Depends(auth.require_company_access)
):
    """
    批次上傳前的預檢：對每個 (path, client_sha256, tags) 交叉查「這家公司底下這個路徑目前
    指向什麼」跟「這個雜湊是不是已經存在這家公司別的地方」，讓前端知道每份文件是
    new/unchanged/content_changed/tags_only_changed/linked，不用實際寫入/重新 embed。
    純讀取（不動向量索引），但比照其他 admin 文件端點一併確認 pgvector 連線正常，行為與其餘
    端點保持一致。

    完全不需要 doc_id：身分判斷全部靠公司+路徑查 kb_document_labels、公司+內容雜湊查
    kb_documents，這兩張表的細節見 app/rag/documents_store.py。
    """
    from app.rag.documents_store import find_document_by_hash, get_label, list_paths_by_prefix

    _get_llamaindex_index()
    try:
        results = []
        seen_paths = set()
        for item in req.items:
            seen_paths.add(item.path)
            label = get_label(company_id, item.path)
            if label is not None and label["content_hash"] == item.client_sha256:
                status: Literal[
                    "new", "unchanged", "content_changed", "tags_only_changed", "linked"
                ] = "unchanged" if set(label["tags"]) == set(item.tags) else "tags_only_changed"
            elif find_document_by_hash(company_id, item.client_sha256) is not None:
                status = "linked"
            elif label is not None:
                status = "content_changed"
            else:
                status = "new"
            results.append(PrecheckResultItem(path=item.path, status=status))

        stale_paths: list[str] = []
        if req.scope_prefix:
            stale_paths = [
                p for p in list_paths_by_prefix(company_id, req.scope_prefix) if p not in seen_paths
            ]
    except Exception as e:
        print(f"[Documents Error] precheck failed: {e}")
        raise HTTPException(status_code=502, detail="預檢知識庫文件時發生錯誤，請稍後再試。")
    return PrecheckResponse(items=results, stale_paths=stale_paths)


@app.put("/api/admin/documents/{path:path}", response_model=DocumentInfo)
def upsert_document(
    path: str,
    tags: list[str] = Form(default=[]),
    client_sha256: str = Form(...),
    file: UploadFile | None = File(default=None),
    company_id: str = Query(...),
    account: dict = Depends(auth.require_company_access),
):
    """
    新增/更新內容/改標籤/掛到既有內容（linked）統一走這支端點，不需要呼叫端提供 doc_id。
    後端依「這家公司底下這個路徑目前指向什麼」跟「這個雜湊是不是已經存在這家公司別的地方」
    決定實際動作，見 app/rag/documents_store.py 的 upsert_document()。平台帳號也能直接修改
    商家的 RAG 資料（非唯讀），跟商家帳號走同一條路徑，差別只在權限檢查（require_company_access
    對 platform 角色一律放行）。

    `file` 只有在真的需要新內容（新文件／內容變更）時才要帶；純改標籤或掛到既有內容
    （雜湊已經存在別處）不需要上傳檔案。帶了 file 的情況一律先驗證雜湊，跟 client_sha256
    不符直接回 400（避免預檢後檔案內容又被改動）。
    """
    from app.rag.documents_store import hash_content, upsert_document as _upsert_document

    index = _get_llamaindex_index()
    raw_text = None
    if file is not None:
        raw_text = _read_md_upload(file)
        _check_client_hash(hash_content(raw_text), client_sha256)
    try:
        result = _upsert_document(company_id, path, tags, client_sha256, raw_text, index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Documents Error] upsert {path} failed: {e}")
        raise HTTPException(status_code=502, detail="新增或更新知識庫文件時發生錯誤，請稍後再試。")
    try:
        accounts_store.record_audit(
            account["id"], action="upsert_document", target_type="kb_document", target_id=path,
            detail={"company_id": company_id, "status": result["status"], "tags": tags},
        )
    except Exception as e:
        # 稽核紀錄失敗不該讓文件已經寫入成功的請求跟著失敗，只印 log。
        print(f"[Audit Error] upsert_document {path} failed to record: {e}")
    return DocumentInfo(
        path=path, tags=tags, chunk_count=result["chunk_count"],
        content_changed=result["content_changed"], content_hash=client_sha256,
    )


@app.delete("/api/admin/documents/{path:path}")
def delete_document(
    path: str, company_id: str = Query(...), account: dict = Depends(auth.require_company_access)
):
    """
    刪除這家公司底下這個路徑的標籤紀錄；該內容如果沒有其他路徑指著了，才真的刪掉向量與內容紀錄
    （見 documents_store.delete_document_by_path()）。
    """
    from app.rag.documents_store import delete_document_by_path

    index = _get_llamaindex_index()
    try:
        deleted = delete_document_by_path(company_id, path, index)
    except Exception as e:
        print(f"[Documents Error] delete {path} failed: {e}")
        raise HTTPException(status_code=502, detail="刪除知識庫文件時發生錯誤，請稍後再試。")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"查無路徑 {path}，請確認路徑是否正確。")
    try:
        accounts_store.record_audit(
            account["id"], action="delete_document", target_type="kb_document", target_id=path,
            detail={"company_id": company_id},
        )
    except Exception as e:
        print(f"[Audit Error] delete_document {path} failed to record: {e}")
    return {"status": "deleted", "path": path}


# ---- 公司（商家服務）管理：/api/admin/companies ----


@app.post("/api/admin/companies", response_model=CompanyInfo)
def create_company(req: CompanyCreateRequest, account: dict = Depends(auth.require_session)):
    """
    任何已登入帳號都能新增企業服務（商家自助開通，不用平台方手動加入），建立後一律自動綁定
    建立者（不分 tenant／platform 角色）：讓一個商家帳號可以自己開多個 company_id；
    管理者帳號建立公司時也綁定，讓「管理者帳號本來就是這家公司的創建者」這件事在公司設定頁
    的協作帳號清單裡看得到、也能正常增減——管理者角色本來就對所有公司有存取權（不靠這個
    綁定），這裡綁定純粹是為了在「這家公司」的視角下如實記錄跟顯示創建者。
    """
    company = accounts_store.create_company(req.name, req.mcp_url, req.welcome_message, req.quick_replies)
    accounts_store.bind_company(account["id"], company["id"])
    accounts_store.record_audit(
        account["id"], action="create_company", target_type="company", target_id=company["id"],
        detail={"name": req.name},
    )
    return CompanyInfo(**company)


@app.get("/api/admin/companies", response_model=CompanyListResponse)
def list_companies(account: dict = Depends(auth.require_session)):
    """回傳呼叫者可見的公司清單：platform 角色看全部，tenant 角色只看自己綁定的。"""
    companies = accounts_store.list_companies_visible_to(account)
    return CompanyListResponse(companies=[CompanyInfo(**c) for c in companies])


@app.put("/api/admin/companies/{company_id}", response_model=CompanyInfo)
def update_company(
    company_id: str, req: CompanyUpdateRequest, account: dict = Depends(auth.require_company_access)
):
    """
    更新公司資訊（name／mcp_url／welcome_message／quick_replies）：platform 帳號或綁定
    這家公司的商家帳號都能改，對應「公司資訊頁面可設定 MCP URL、聊天機器人開頭語、
    開場快速提問」的需求。
    """
    company = accounts_store.update_company(
        company_id, req.name, req.mcp_url, req.welcome_message, req.quick_replies
    )
    if company is None:
        raise HTTPException(status_code=404, detail="查無這家公司。")
    accounts_store.record_audit(
        account["id"], action="update_company", target_type="company", target_id=company_id,
        detail={
            "name": req.name, "mcp_url": req.mcp_url, "welcome_message": req.welcome_message,
            "quick_replies": req.quick_replies,
        },
    )
    return CompanyInfo(**company)


@app.delete("/api/admin/companies/{company_id}")
def delete_company(company_id: str, account: dict = Depends(auth.require_company_access)):
    """
    硬刪除公司：platform 角色或綁定這家公司的商家帳號都能刪除（比照 update_company 的權限
    模型）——商家自助建立公司後，理當也能自己刪除，不用另外找平台方。連同該公司的 RAG
    文件記錄與向量 chunk 一起清掉（見 documents_store.purge_company()），company_accounts
    綁定靠 ON DELETE CASCADE 自動清。
    """
    from app.rag.documents_store import purge_company

    index = _get_llamaindex_index()
    deleted = accounts_store.delete_company(company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="查無這家公司。")
    try:
        purge_company(company_id, index)
    except Exception as e:
        # 公司本身已經刪除成功；RAG 資料清理失敗只印 log，不讓整個刪除請求回錯誤
        # （避免呼叫端誤以為公司沒刪成功而重試，造成後續 accounts_store.delete_company 再次回 404 的困惑）。
        print(f"[Company Delete Error] purge_company {company_id} failed: {e}")
    accounts_store.record_audit(
        account["id"], action="delete_company", target_type="company", target_id=company_id,
    )
    return {"status": "deleted", "company_id": company_id}


# ---- 帳號管理：/api/admin/accounts（主帳號/主開發者新增次帳號/次開發者） ----


def _can_manage_account_for(actor: dict, req: AccountCreateRequest) -> bool:
    """
    新增/移除帳號的權限判斷：
    - 新增 platform_secondary：僅限 platform_primary。
    - 新增 tenant_*（綁定某 company）：呼叫者對該 company 要有存取權
      （platform 角色，或 tenant_primary/tenant_secondary 且已綁定該公司——見實作計畫，
      次帳號權限跟主帳號相同，差別只在誰能新增/移除誰，這裡不特別區分 primary/secondary）。
    """
    if req.role == "platform_primary":
        return False  # 不開放透過 API 新增第二個 platform_primary，避免權限模型混亂
    if req.role == "platform_secondary":
        return actor["role"] == "platform_primary"
    # tenant_primary / tenant_secondary
    if not req.company_id:
        return False
    return accounts_store.account_has_company_access(actor, req.company_id)


@app.post("/api/admin/accounts", response_model=AccountInfo)
def create_account(req: AccountCreateRequest, actor: dict = Depends(auth.require_session)):
    if not _can_manage_account_for(actor, req):
        raise HTTPException(status_code=403, detail="沒有權限新增這個角色的帳號。")
    if accounts_store.get_account_by_email(req.email) is not None:
        raise HTTPException(status_code=400, detail="這個 email 已經是系統帳號了。")
    account = accounts_store.create_account(req.email, req.role, actor["id"])
    if req.role in accounts_store.TENANT_ROLES and req.company_id:
        accounts_store.bind_company(account["id"], req.company_id)
    accounts_store.record_audit(
        actor["id"], action="create_account", target_type="account", target_id=account["id"],
        detail={"email": req.email, "role": req.role, "company_id": req.company_id},
    )
    return AccountInfo(**account)


@app.get("/api/admin/accounts", response_model=AccountListResponse)
def list_accounts(company_id: str | None = Query(default=None), actor: dict = Depends(auth.require_session)):
    """
    帶 company_id：回傳這家公司綁定的商家帳號（公司設定頁「管理帳號」用），呼叫者要對這家
    公司有存取權，比照 update_company／audit-log 的權限模式；不含管理者帳號，天生就不會
    混進其他公司的協作帳號。
    不帶 company_id：回傳所有管理者帳號（platform_primary／platform_secondary，「管理者
    帳號」頁籤用），僅限 platform 角色呼叫，商家帳號沒有理由要看到管理者帳號清單。
    """
    if company_id:
        if not accounts_store.account_has_company_access(actor, company_id):
            raise HTTPException(status_code=403, detail="沒有這家公司的存取權限。")
        accounts = accounts_store.list_accounts_for_company(company_id)
    else:
        if actor["role"] not in accounts_store.PLATFORM_ROLES:
            raise HTTPException(status_code=403, detail="此操作僅限平台維運帳號。")
        accounts = accounts_store.list_platform_accounts()
    return AccountListResponse(accounts=[AccountInfo(**a) for a in accounts])


@app.delete("/api/admin/accounts/{account_id}")
def delete_account(account_id: str, actor: dict = Depends(auth.require_session)):
    """
    刪除帳號：權限比照新增（platform_primary 能刪 platform_secondary；對某公司有存取權的帳號
    能刪同公司的 tenant 帳號）。刪除後連帶清掉該帳號所有 sessions（ON DELETE CASCADE），
    達成「移除次帳號時立刻讓對方 session 失效」。
    """
    target = accounts_store.get_account_by_id(account_id)
    if target is None:
        raise HTTPException(status_code=404, detail="查無這個帳號。")
    if target["role"] == "platform_primary":
        raise HTTPException(status_code=403, detail="不能透過 API 刪除 platform_primary 帳號。")
    if target["role"] == "platform_secondary":
        if actor["role"] != "platform_primary":
            raise HTTPException(status_code=403, detail="沒有權限刪除這個帳號。")
    else:
        # tenant_* 帳號：呼叫者要對這個帳號目前綁定的任一家公司有存取權才能刪
        companies = accounts_store.list_companies_visible_to(target)
        if actor["role"] not in accounts_store.PLATFORM_ROLES and not any(
            accounts_store.account_has_company_access(actor, c["id"]) for c in companies
        ):
            raise HTTPException(status_code=403, detail="沒有權限刪除這個帳號。")
    target_companies = accounts_store.list_companies_visible_to(target) if target["role"] in accounts_store.TENANT_ROLES else []
    accounts_store.delete_account(account_id)
    accounts_store.record_audit(
        actor["id"], action="delete_account", target_type="account", target_id=account_id,
        detail={
            "email": target["email"],
            # 只記第一家，稽核頁面用這個欄位做 company_id 過濾；帳號同時綁多家公司是少數情況，
            # 這裡不為了這個邊角案例把 detail 改成陣列、多寫一套查詢邏輯。
            "company_id": target_companies[0]["id"] if target_companies else None,
        },
    )
    return {"status": "deleted", "account_id": account_id}


# ---- 稽核紀錄：/api/admin/audit-log（依 company_id 查這家公司相關的異動紀錄） ----


@app.get("/api/admin/audit-log", response_model=AuditLogListResponse)
def get_audit_log(company_id: str = Query(...), _account: dict = Depends(auth.require_company_access)):
    """
    查一家公司的稽核紀錄：權限比照 /api/admin/summary，只有 platform 帳號或綁定這家公司的
    帳號才能看。內容涵蓋公司異動、RAG 文件上傳/刪除、這家公司協作帳號的新增/移除。
    """
    entries = accounts_store.list_audit_log_for_company(company_id)
    return AuditLogListResponse(entries=[AuditLogEntry(**e) for e in entries])


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, _client_id: str = Depends(_require_client_id)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    _check_company_rate_limit(_client_id)

    text = req.message.strip()
    history = [{"role": h.role, "content": h.content} for h in req.history]
    history = history[-(settings.MAX_HISTORY_TURNS * 2):]
    try:
        # X-Client-ID（_client_id）現在就是 companies 表的 company_id（見
        # sourcecode/chat-widget/README.md 的 data-client-id 說明）；沒對應到任何公司時
        # 檢索合理地回傳空結果（不是錯誤），不影響其他訂單分流邏輯。
        response = await _handle_chat(text, history, req.provider, company_id=_client_id)
    except Exception as e:
        # 任何未預期的例外（金鑰失效、首次建索引逾時等）都要回傳正常的 200 回應，
        # 讓 FastAPI/CORSMiddleware 有機會處理，避免請求整個掛掉變成 Cloud Run
        # 的 502/503（那種回應不是應用程式產生的，不會帶 CORS 標頭，前端只會看到 CORS 錯誤）。
        print(f"[Chat Error] {e}")
        response = ChatResponse(type="text", text="系統暫時發生錯誤，請稍後再試或聯繫真人客服（0800-123-456）。")

    try:
        log_text = response.text if response.text is not None else f"[訂單 {response.code}]"
        log_chat(
            message=text, response_type=response.type, response_text=log_text, client_ip=client_ip,
            company_id=_client_id,
        )
    except Exception:
        # 對話紀錄失敗不該讓使用者的聊天請求跟著失敗
        pass

    return response


def _lookup_company(company_id: str | None) -> dict | None:
    """
    company_id 來自未經驗證的 X-Client-ID header，可能是 None、空字串，或格式不合法的
    UUID；accounts_store.get_company() 底層是 Postgres 查詢，帶入不合法 UUID 會直接拋
    例外，這裡統一包一層防呆，查不到／格式不對都當作「查無公司」，不能讓呼叫端的請求
    跟著炸掉。widget_config() 與 _handle_chat() 的訂單查詢分流都靠這個函式取得公司資料。
    """
    if not company_id:
        return None
    try:
        return accounts_store.get_company(company_id)
    except Exception:
        return None


async def _handle_chat(
    text: str, history: list, provider: str, company_id: str | None = None
) -> ChatResponse:
    if not text:
        return ChatResponse(type="text", text="請輸入您的問題。")

    match = ORDER_CODE_PATTERN.search(text.upper())
    if match or "訂單" in text:
        if match is None:
            return ChatResponse(
                type="text",
                text="請提供訂單編號（例如 A12345 或 ORD-500001）以便查詢。",
            )
        code = match.group(0)
        company = _lookup_company(company_id)
        if not company or not company.get("mcp_url"):
            # 沒有對應公司，或公司沒填 mcp_url：這家服務沒開訂單查詢功能，不落到 SQLite
            # fallback（那是全域 demo 資料，跟任何一家真的公司無關，不該冒充出現）。
            return ChatResponse(
                type="text",
                text="此服務目前尚未提供訂單查詢功能，如需協助請聯繫客服（0800-123-456）。",
            )
        order = await get_order(code, company["mcp_url"])
        if order is None:
            return ChatResponse(
                type="text",
                text=f"查無訂單編號 {code}，請確認編號是否正確，或聯繫真人客服（0800-123-456）。",
            )
        return ChatResponse(
            type="order",
            code=code,
            status=order["status"],
            eta=order["eta"],
            items=order["items"],
        )

    agent = get_agent()
    answer, retrieved = agent.generate_answer(text, history=history, provider=provider, company_id=company_id)
    if not retrieved:
        # 沒有實際檢索結果（查無資訊、provider 未設定或呼叫失敗）：這是提示/錯誤訊息，不是
        # 根據知識庫生成的產品/政策回答，依 contracts.md 的分類該用 type: text，且不該帶無關的 source。
        return ChatResponse(type="text", text=answer)
    top_source = retrieved[0]["topic"]
    return ChatResponse(type="product", text=answer, source=top_source, sources=retrieved)

# LINE Messaging API
app.include_router(create_line_router(_handle_chat))