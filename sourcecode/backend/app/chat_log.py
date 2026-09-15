"""
對話紀錄：把每次 /api/chat 問答存進 SQLite，作為未來「管理者摘要當日提問」功能的資料來源。

先用 SQLite（單檔案，不需要額外服務），流量大到需要多台伺服器共用時再換 Postgres 等方案。
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

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
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.CHAT_LOG_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _ensure_company_id_column(conn: sqlite3.Connection) -> None:
    """
    company_id 是後補的欄位（多租戶摘要功能要依公司過濾）；chat_log.db 可能是舊版留下來的
    檔案，沒有這個欄位。SQLite 的 ADD COLUMN 不支援 IF NOT EXISTS，用 PRAGMA table_info
    查有沒有這個欄位，沒有才補（冪等，每次呼叫都查一次，開銷很小，不特別另外快取）。
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_log)").fetchall()}
    if "company_id" not in columns:
        conn.execute("ALTER TABLE chat_log ADD COLUMN company_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_log_company_id ON chat_log (company_id)")


def init_db():
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _ensure_company_id_column(conn)
        conn.commit()


def log_chat(
    message: str, response_type: str, response_text: str | None, client_ip: str | None,
    company_id: str | None = None,
):
    """寫入失敗不應該影響聊天功能本身，呼叫端負責 try/except。"""
    with _connect() as conn:
        _ensure_company_id_column(conn)
        conn.execute(
            "INSERT INTO chat_log (created_at, client_ip, message, response_type, response_text, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), client_ip, message, response_type, response_text, company_id),
        )
        conn.commit()


def get_messages_for_date(date: str, company_id: str) -> list[str]:
    """
    取得指定日期（YYYY-MM-DD，UTC）、指定公司當天所有使用者提問的原始文字，依時間排序。
    company_id 必填——摘要依公司隔離，不提供全域彙總（避免看到其他公司的顧客提問內容）。
    """
    with _connect() as conn:
        _ensure_company_id_column(conn)
        rows = conn.execute(
            "SELECT message FROM chat_log WHERE created_at LIKE ? AND company_id = ? ORDER BY created_at",
            (f"{date}%", company_id),
        ).fetchall()
    return [row[0] for row in rows]
