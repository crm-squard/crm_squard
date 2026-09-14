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

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DailySummaryResponse,
    DocumentInfo,
    DocumentListResponse,
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


def _check_rate_limit(client_ip: str):
    now = time.time()
    timestamps = _request_log[client_ip]
    while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="請求過於頻繁，請稍後再試。")
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


@app.get("/api/widget/config", response_model=WidgetConfig)
def widget_config(_client_id: str = Depends(_require_client_id)):
    """MVP 先提供共用樣式；之後可在此依 client ID 讀取客戶品牌設定。"""
    return WidgetConfig(
        brand_name="線上客服",
        welcome_message="您好，我是線上客服，可以問我任何產品的規格、特色，或是輸入訂單編號查詢配送狀態喔。",
        logo_url=None,
        theme=WidgetTheme(
            primary_color="#315b7d",
            surface_color="#ffffff",
            text_color="#17212b",
            border_radius=20,
        ),
    )


@app.get("/api/admin/summary", response_model=DailySummaryResponse)
def admin_summary(date: str | None = None):
    """
    管理者查看指定日期（預設今天，UTC）使用者提問的主題摘要。

    注意：目前沒有任何身分驗證，正式上線前必須加上管理者登入/權限檢查，
    否則任何人都能呼叫這支 API 看到顧客提問內容。
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    elif not DATE_PATTERN.match(date):
        raise HTTPException(status_code=400, detail="date 格式須為 YYYY-MM-DD")

    try:
        result = summarize_day(date)
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
def list_documents():
    """
    列出知識庫目前所有路徑（一份內容掛兩個路徑就是兩列，各自標籤），供管理頁面畫列表。

    注意：目前沒有任何身分驗證，正式上線前必須加上管理者登入/權限檢查（同 /api/admin/summary）。
    """
    from app.rag.documents_store import list_documents as _list_documents

    _get_llamaindex_index()  # 確認 pgvector 連線正常，不通就提早回錯誤
    try:
        docs = _list_documents()
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
def precheck_documents(req: PrecheckRequest):
    """
    批次上傳前的預檢：對每個 (path, client_sha256, tags) 交叉查「這個路徑目前指向什麼」跟
    「這個雜湊是不是已經存在別的地方」，讓前端知道每份文件是 new/unchanged/content_changed/
    tags_only_changed/linked，不用實際寫入/重新 embed。純讀取（不動向量索引），但比照其他
    admin 文件端點一併確認 pgvector 連線正常，行為與其餘端點保持一致。

    完全不需要 doc_id：身分判斷全部靠路徑查 kb_document_labels、內容雜湊查 kb_documents，
    這兩張表的細節見 app/rag/documents_store.py。
    """
    from app.rag.documents_store import find_document_by_hash, get_label, list_paths_by_prefix

    _get_llamaindex_index()
    try:
        results = []
        seen_paths = set()
        for item in req.items:
            seen_paths.add(item.path)
            label = get_label(item.path)
            if label is not None and label["content_hash"] == item.client_sha256:
                status: Literal[
                    "new", "unchanged", "content_changed", "tags_only_changed", "linked"
                ] = "unchanged" if set(label["tags"]) == set(item.tags) else "tags_only_changed"
            elif find_document_by_hash(item.client_sha256) is not None:
                status = "linked"
            elif label is not None:
                status = "content_changed"
            else:
                status = "new"
            results.append(PrecheckResultItem(path=item.path, status=status))

        stale_paths: list[str] = []
        if req.scope_prefix:
            stale_paths = [p for p in list_paths_by_prefix(req.scope_prefix) if p not in seen_paths]
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
):
    """
    新增/更新內容/改標籤/掛到既有內容（linked）統一走這支端點，不需要呼叫端提供 doc_id。
    後端依「這個路徑目前指向什麼」跟「這個雜湊是不是已經存在別的地方」決定實際動作，
    見 app/rag/documents_store.py 的 upsert_document()。

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
        result = _upsert_document(path, tags, client_sha256, raw_text, index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Documents Error] upsert {path} failed: {e}")
        raise HTTPException(status_code=502, detail="新增或更新知識庫文件時發生錯誤，請稍後再試。")
    return DocumentInfo(
        path=path, tags=tags, chunk_count=result["chunk_count"],
        content_changed=result["content_changed"], content_hash=client_sha256,
    )


@app.delete("/api/admin/documents/{path:path}")
def delete_document(path: str):
    """
    刪除這個路徑的標籤紀錄；該內容如果沒有其他路徑指著了，才真的刪掉向量與內容紀錄
    （見 documents_store.delete_document_by_path()）。
    """
    from app.rag.documents_store import delete_document_by_path

    index = _get_llamaindex_index()
    try:
        deleted = delete_document_by_path(path, index)
    except Exception as e:
        print(f"[Documents Error] delete {path} failed: {e}")
        raise HTTPException(status_code=502, detail="刪除知識庫文件時發生錯誤，請稍後再試。")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"查無路徑 {path}，請確認路徑是否正確。")
    return {"status": "deleted", "path": path}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, _client_id: str = Depends(_require_client_id)):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    text = req.message.strip()
    history = [{"role": h.role, "content": h.content} for h in req.history]
    history = history[-(settings.MAX_HISTORY_TURNS * 2):]
    try:
        response = await _handle_chat(text, history, req.provider)
    except Exception as e:
        # 任何未預期的例外（金鑰失效、首次建索引逾時等）都要回傳正常的 200 回應，
        # 讓 FastAPI/CORSMiddleware 有機會處理，避免請求整個掛掉變成 Cloud Run
        # 的 502/503（那種回應不是應用程式產生的，不會帶 CORS 標頭，前端只會看到 CORS 錯誤）。
        print(f"[Chat Error] {e}")
        response = ChatResponse(type="text", text="系統暫時發生錯誤，請稍後再試或聯繫真人客服（0800-123-456）。")

    try:
        log_text = response.text if response.text is not None else f"[訂單 {response.code}]"
        log_chat(message=text, response_type=response.type, response_text=log_text, client_ip=client_ip)
    except Exception:
        # 對話紀錄失敗不該讓使用者的聊天請求跟著失敗
        pass

    return response


async def _handle_chat(text: str, history: list, provider: str) -> ChatResponse:
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
        order = await get_order(code)
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
    answer, retrieved = agent.generate_answer(text, history=history, provider=provider)
    if not retrieved:
        # 沒有實際檢索結果（查無資訊、provider 未設定或呼叫失敗）：這是提示/錯誤訊息，不是
        # 根據知識庫生成的產品/政策回答，依 contracts.md 的分類該用 type: text，且不該帶無關的 source。
        return ChatResponse(type="text", text=answer)
    top_source = retrieved[0]["topic"]
    return ChatResponse(type="product", text=answer, source=top_source, sources=retrieved)

# LINE Messaging API
app.include_router(create_line_router(_handle_chat))