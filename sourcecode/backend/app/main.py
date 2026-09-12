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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import ChatRequest, ChatResponse, DailySummaryResponse, ProviderInfo
from app.agent import get_agent
from app.orders import get_order, init_db as init_orders_db
from app.chat_log import init_db as init_chat_log_db, log_chat
from app.summary import summarize_day
from app.providers import is_configured
from app.line_webhook import create_line_router

PROVIDER_LABELS = {
    "local": "本地 MiniCPM5-2B（免費，速度較慢）",
    "anthropic": "Claude",
    "openai": "GPT",
    "google": "Gemini",
    "xai": "Grok",
}

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/warmup")
def warmup():
    """手動觸發載入 Embedding / LLM 模型，避免第一次聊天時使用者要空等模型下載。"""
    get_agent()
    return {"status": "models loaded"}


@app.get("/api/providers", response_model=list[ProviderInfo])
def list_providers():
    """前端聊天視窗用來畫「選擇回答模型」下拉選單，含每個 provider 有沒有設定 key。"""
    return [
        ProviderInfo(id=pid, label=label, configured=is_configured(pid))
        for pid, label in PROVIDER_LABELS.items()
    ]


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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
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
