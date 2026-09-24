"""
對話紀錄：把每次 /api/chat 問答存進 SQLite，作為未來「管理者摘要當日提問」功能的資料來源。

先用 SQLite（單檔案，不需要額外服務），流量大到需要多台伺服器共用時再換 Postgres 等方案。
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    client_ip TEXT,
    message TEXT NOT NULL,
    response_type TEXT NOT NULL,
    response_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_log_created_at ON chat_log (created_at);

-- @mcp 對話中 LLM 實際呼叫過的 MCP tool（稽核用：哪家公司、呼叫了哪個 tool、帶了什麼參數）。
-- 只記參數，不記 tool 回傳內容（回傳可能含顧客資料）。arguments 是 JSON 字串。
CREATE TABLE IF NOT EXISTS mcp_tool_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    chatbot_id TEXT,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    is_error INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_log_chatbot_id ON mcp_tool_log (chatbot_id, created_at);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.CHAT_LOG_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _ensure_chatbot_id_column(conn: sqlite3.Connection) -> None:
    """
    chatbot_id 是後補的欄位（多租戶摘要功能要依公司過濾）；chat_log.db 可能是舊版留下來的
    檔案，沒有這個欄位。SQLite 的 ADD COLUMN 不支援 IF NOT EXISTS，用 PRAGMA table_info
    查有沒有這個欄位，沒有才補（冪等，每次呼叫都查一次，開銷很小，不特別另外快取）。
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_log)").fetchall()}
    if "chatbot_id" not in columns:
        conn.execute("ALTER TABLE chat_log ADD COLUMN chatbot_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_log_chatbot_id ON chat_log (chatbot_id)")


def init_db():
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _ensure_chatbot_id_column(conn)
        conn.commit()


def log_chat(
    message: str, response_type: str, response_text: str | None, client_ip: str | None,
    chatbot_id: str | None = None,
):
    """寫入失敗不應該影響聊天功能本身，呼叫端負責 try/except。"""
    with _connect() as conn:
        _ensure_chatbot_id_column(conn)
        conn.execute(
            "INSERT INTO chat_log (created_at, client_ip, message, response_type, response_text, chatbot_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), client_ip, message, response_type, response_text, chatbot_id),
        )
        conn.commit()


def log_tool_calls(chatbot_id: str | None, tool_calls) -> None:
    """
    記錄一次 @mcp 對話裡 LLM 呼叫過的每個 tool。chat_log.db 可能是舊版留下來的檔案，
    沒有 mcp_tool_log 表，所以每次寫入前用 IF NOT EXISTS 確保存在（冪等）。
    寫入失敗不應該影響聊天功能本身，呼叫端負責 try/except。
    """
    if not tool_calls:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT INTO mcp_tool_log (created_at, chatbot_id, tool_name, arguments, is_error) VALUES (?, ?, ?, ?, ?)",
            [
                (now, chatbot_id, c.name, json.dumps(c.arguments, ensure_ascii=False), int(c.is_error))
                for c in tool_calls
            ],
        )
        conn.commit()


def get_tool_calls_for_chatbot(chatbot_id: str, limit: int = 100) -> list[dict]:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        rows = conn.execute(
            "SELECT created_at, tool_name, arguments, is_error FROM mcp_tool_log "
            "WHERE chatbot_id = ? ORDER BY id DESC LIMIT ?",
            (chatbot_id, limit),
        ).fetchall()
    return [
        {"created_at": r[0], "tool_name": r[1], "arguments": json.loads(r[2]), "is_error": bool(r[3])}
        for r in rows
    ]


def get_messages_for_range(start_date: str, end_date: str, chatbot_id: str) -> list[dict]:
    """
    取得指定 UTC 日期區間（YYYY-MM-DD，含起日與結束日）、指定公司所有使用者提問，依時間排序。
    chatbot_id 必填——摘要依公司隔離，不提供全域彙總（避免看到其他公司的顧客提問內容）。

    同時回傳 response_text：summary.py 用它判斷機器人當時是不是回「查無此資訊」
    （app.agent.NO_INFO_ANSWER），藉此輔助分類「需商家關注」的問題，不用完全依賴 LLM 自己判斷。
    """
    end_exclusive = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    with _connect() as conn:
        _ensure_chatbot_id_column(conn)
        rows = conn.execute(
            "SELECT message, response_text FROM chat_log "
            "WHERE created_at >= ? AND created_at < ? AND chatbot_id = ? "
            "ORDER BY created_at",
            (start_date, end_exclusive, chatbot_id),
        ).fetchall()
    return [{"message": row[0], "response_text": row[1]} for row in rows]
