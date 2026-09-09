"""
訂單資料（對應提案 #2「顧客查詢訂單」的資料來源）。

真正的訂單資料來源是 corp-backend（接 GCP Firestore），這裡透過 MCP
（Streamable HTTP transport）呼叫 corp-backend 的 get_order tool。
corp-backend 連不上或查詢失敗時，退回本機 SQLite（orders.db，mock 資料）當 fallback，
確保聊天服務不會因為 corp-backend 掛掉就整條訂單查詢路徑壞掉。

orders.db 的 SQLite 邏輯保留，原本是唯一資料來源時的實作，現在只在 MCP 呼叫失敗時當備援用。

status 對應前端時間軸的階段索引：
  0 = 已下單, 1 = 備貨出貨, 2 = 配送中, 3 = 已送達
"""
import json
import logging
import sqlite3
from contextlib import contextmanager

from mcp.client.session import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.shared.exceptions import MCPError

from app.config import settings

logger = logging.getLogger("backend.orders")

# corp-backend（Firestore）的 Status 是任意字串，這裡對應回前端時間軸用的 0-3 階段索引。
# 目前 corp-backend 測試資料觀察到的值先列在這，corp-backend 之後若擴充狀態值要一併補進來；
# 對應不到的狀態預設當作「已下單」，不擋住查詢結果。
_CORP_STATUS_TO_STAGE = {
    "pending": 0,
    "processing": 1,
    "shipped": 2,
    "delivered": 3,
    "completed": 3,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    code TEXT PRIMARY KEY,
    status INTEGER NOT NULL,
    eta TEXT NOT NULL,
    items TEXT NOT NULL
);
"""

# 範例資料，模擬真實訂單系統裡會有的紀錄
_SEED_ORDERS = [
    ("A12345", 2, "8月28日", "智慧掃地機器人 R5 Pro ×1"),
    ("B98231", 0, "9月5日", "智慧冷氣 A8（1.5噸）×1"),
    ("C55210", 3, "已送達", "智慧電視 V6 55吋 ×1"),
    ("D77102", 1, "9月8日", "智慧掃地機器人 R5 Pro ×2、智慧電視 V6 43吋 ×1"),
    ("E30044", 2, "9月4日", "智慧冷氣 A8（2.2噸）×1"),
]


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.ORDERS_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO orders (code, status, eta, items) VALUES (?, ?, ?, ?)",
                _SEED_ORDERS,
            )
        conn.commit()


def _get_order_from_sqlite(code: str):
    """MCP 查詢失敗時的 fallback，查本機 orders.db 的 mock 資料。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT status, eta, items FROM orders WHERE code = ?",
            (code.upper(),),
        ).fetchone()
    if row is None:
        return None
    status, eta, items = row
    return {"status": status, "eta": eta, "items": items}


async def _get_order_via_mcp(code: str):
    """
    透過 MCP Streamable HTTP 呼叫 corp-backend 的 get_order tool。
    stateless_http 模式下不用維護長連線，每次查詢開一段短連線，函式結束就自動關閉。

    mcp==2.0.0b2（v2 beta）備註：跟官方 migration guide 描述的不同，
    `streamable_http_client()` 回傳的仍是 `(read_stream, write_stream)` 這種底層 stream
    tuple（而非直接可用的 session 物件），實測過還是要照 v1 的方式包一層
    `ClientSession(read, write)` 並呼叫 `await session.initialize()` 完成 handshake，
    跳過這步 `call_tool()` 會因為沒有協定版本可用而失敗。這點已在改版時實測驗證過，
    並非沿用舊寫法未更新。

    `create_mcp_http_client()` 是 SDK 提供的 httpx2.AsyncClient 便利建構函式，預設開啟
    follow_redirects=True；corp-backend 把 MCP app mount 在 "/mcp"（見 app/main.py），
    Starlette 對到子路徑 "/" 的請求（也就是 CORP_BACKEND_MCP_URL 不帶結尾斜線時）
    會先回 307 導到 "/mcp/"，沒有 follow_redirects 的話 POST 會直接失敗
    （實測驗證過，並非理論推測）。若改用手動建立的 httpx2.AsyncClient 記得也要開這個選項。
    """
    http_client = create_mcp_http_client()
    async with streamable_http_client(settings.CORP_BACKEND_MCP_URL, http_client=http_client) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_order", {"order_id": code.upper()})

    # v2 的欄位命名從 camelCase 改成 snake_case：isError -> is_error、
    # structuredContent -> structured_content。工具內主動 raise MCPError 的情況
    # （見 corp-backend/app/mcp_server.py）在 call_tool() 這層就會直接拋出例外，
    # 不會走到這裡的 is_error 分支；這裡保留 is_error 檢查是防禦性寫法，
    # 涵蓋工具框架自己接住一般例外、包成 is_error=True 回傳的情況。
    if result.is_error:
        raise RuntimeError(f"corp-backend MCP get_order 回傳錯誤: {result.content}")

    if result.structured_content is not None:
        order = result.structured_content.get("result", result.structured_content)
    elif result.content:
        # 部分回傳型別（例如 Union）不會產生 structured_content，退回解析文字內容的 JSON
        order = json.loads(result.content[0].text)
    else:
        order = None
    if order is None:
        return None

    status_str = str(order.get("Status", "")).strip().lower()
    stage = _CORP_STATUS_TO_STAGE.get(status_str, 0)
    return {"status": stage, "eta": order.get("OrderDate"), "items": order.get("ProductName")}


async def get_order(code: str):
    try:
        return await _get_order_via_mcp(code)
    except MCPError as e:
        # 工具執行失敗（業務錯誤，例如 corp-backend 讀取 Firestore 失敗）：
        # corp-backend 端的工具會 raise MCPError，這裡明確接住並 fallback。
        logger.warning(f"corp-backend MCP 工具執行失敗，改用本機 SQLite fallback: {e}")
        return _get_order_from_sqlite(code)
    except Exception as e:
        # 連線層級的例外（corp-backend 整個連不上、逾時等），不是 MCPError，
        # 保留這層當最後防線。
        logger.warning(f"corp-backend MCP 查詢訂單失敗，改用本機 SQLite fallback: {e}")
        return _get_order_from_sqlite(code)
