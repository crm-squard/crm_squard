"""
多租戶帳號核心邏輯：companies（商家服務）/ accounts（帳號）/ company_accounts（帳號-公司
綁定）/ sessions（登入 session）/ audit_log（稽核紀錄）這五張表的 schema 與存取函式。

架構比照 app/rag/documents_store.py 的風格：raw SQL（sqlalchemy.text()）、模組層級
_schema_ready flag 做冪等 CREATE TABLE IF NOT EXISTS，不用 ORM／migration 框架，
跟現有專案的資料層慣例一致；跟 documents_store.py 共用 app/db.py 的同一個 Engine
（同一個 Postgres 資料庫）。

兩層帳號角色（accounts.role）：
- platform_primary / platform_secondary：服務方（平台維運）帳號，看得到所有商家服務。
- tenant_primary / tenant_secondary：商家帳號，只看得到自己綁定（company_accounts）的公司；
  一個 tenant_primary 可以綁多家 company，tenant_secondary 權限跟 primary 相同，差別只在
  「誰能新增/移除誰」（見 main.py 的 /api/admin/accounts 權限判斷）。

session 只存 token 的 SHA-256 雜湊（不存明文），避免資料庫外洩就等於外洩所有人的登入憑證；
明文 token 只在 create_session() 當下回傳給呼叫端一次。
"""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text as sql_text

from app.config import settings
from app.db import get_engine

_schema_ready = False


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    engine = get_engine()
    with engine.begin() as conn:
        # pgcrypto 提供 gen_random_uuid()；Supabase/多數雲端 Postgres 預設就有裝，
        # CREATE EXTENSION IF NOT EXISTS 是冪等操作，沒有權限時忽略即可（多半已經裝好）。
        try:
            conn.execute(sql_text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        except Exception:
            pass
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name       TEXT NOT NULL,
                mcp_url    TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ))
        # companies 表已經有真實資料（商家自己建立的公司），不能用「砍掉重建」的方式加欄位；
        # 用 ALTER TABLE ADD COLUMN IF NOT EXISTS 冪等地補上 welcome_message
        # （聊天機器人開頭語，取代 main.py 原本寫死的字串，見 widget_config()）。
        conn.execute(sql_text(
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS welcome_message TEXT"
        ))
        # quick_replies：開場快速提問清單（原本 chat-widget 寫死 3 題），存成 JSON 陣列字串
        # （TEXT 欄位），比另開一張子表簡單，反正只是一份不需要單獨查詢/索引的小清單。
        conn.execute(sql_text(
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS quick_replies TEXT"
        ))
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email      TEXT NOT NULL UNIQUE,
                role       TEXT NOT NULL CHECK (
                    role IN ('platform_primary', 'platform_secondary', 'tenant_primary', 'tenant_secondary')
                ),
                created_by UUID REFERENCES accounts(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ))
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS company_accounts (
                account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (account_id, company_id)
            )
            """
        ))
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at TIMESTAMPTZ NOT NULL
            )
            """
        ))
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id               BIGSERIAL PRIMARY KEY,
                actor_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
                action           TEXT NOT NULL,
                target_type      TEXT NOT NULL,
                target_id        TEXT,
                detail           JSONB,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ))
        conn.execute(sql_text(
            "CREATE INDEX IF NOT EXISTS sessions_account_id_idx ON sessions (account_id)"
        ))
        conn.execute(sql_text(
            "CREATE INDEX IF NOT EXISTS company_accounts_company_id_idx ON company_accounts (company_id)"
        ))
    _schema_ready = True
    bootstrap_initial_platform_admins()


PLATFORM_ROLES = {"platform_primary", "platform_secondary"}
TENANT_ROLES = {"tenant_primary", "tenant_secondary"}


def _row_to_account(row) -> dict:
    return {
        "id": str(row.id),
        "email": row.email,
        "role": row.role,
        "created_by": str(row.created_by) if row.created_by is not None else None,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def get_account_by_email(email: str) -> Optional[dict]:
    _ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql_text("SELECT id, email, role, created_by, created_at FROM accounts WHERE email = :email"),
            {"email": email},
        ).fetchone()
    return _row_to_account(row) if row is not None else None


def get_account_by_id(account_id: str) -> Optional[dict]:
    _ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql_text("SELECT id, email, role, created_by, created_at FROM accounts WHERE id = :id"),
            {"id": account_id},
        ).fetchone()
    return _row_to_account(row) if row is not None else None


def create_account(email: str, role: str, created_by: Optional[str]) -> dict:
    """新增一個帳號（次帳號/次開發者新增立即生效，不用寄信確認）。email 全域唯一。"""
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text(
                """
                INSERT INTO accounts (email, role, created_by)
                VALUES (:email, :role, :created_by)
                RETURNING id, email, role, created_by, created_at
                """
            ),
            {"email": email, "role": role, "created_by": created_by},
        ).fetchone()
    return _row_to_account(row)


def delete_account(account_id: str) -> bool:
    """刪除帳號；ON DELETE CASCADE 會連帶刪掉 company_accounts／sessions，
    達成「移除次帳號時立刻讓對方 session 失效」（不是等 token 自然過期）。"""
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text("DELETE FROM accounts WHERE id = :id RETURNING id"), {"id": account_id}
        ).fetchone()
    return row is not None


def list_accounts_visible_to(account: dict) -> list[dict]:
    """platform 角色看得到全部帳號；tenant 角色只看得到跟自己綁定同一家 company 的帳號
    （含自己）——比照「商家主帳號能管理自己商家底下的次帳號」的權限模型。"""
    _ensure_schema()
    engine = get_engine()
    if account["role"] in PLATFORM_ROLES:
        sql = sql_text("SELECT id, email, role, created_by, created_at FROM accounts ORDER BY created_at")
        params = {}
    else:
        sql = sql_text(
            """
            SELECT DISTINCT a.id, a.email, a.role, a.created_by, a.created_at
            FROM accounts a
            JOIN company_accounts ca ON ca.account_id = a.id
            WHERE ca.company_id IN (
                SELECT company_id FROM company_accounts WHERE account_id = :account_id
            )
            ORDER BY a.created_at
            """
        )
        params = {"account_id": account["id"]}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_account(r) for r in rows]


def bind_company(account_id: str, company_id: str) -> None:
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                """
                INSERT INTO company_accounts (account_id, company_id)
                VALUES (:account_id, :company_id)
                ON CONFLICT (account_id, company_id) DO NOTHING
                """
            ),
            {"account_id": account_id, "company_id": company_id},
        )


def unbind_company(account_id: str, company_id: str) -> None:
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                "DELETE FROM company_accounts WHERE account_id = :account_id AND company_id = :company_id"
            ),
            {"account_id": account_id, "company_id": company_id},
        )


def account_has_company_access(account: dict, company_id: str) -> bool:
    """platform 角色對任何公司都有存取權；tenant 角色要查 company_accounts 有沒有綁定。"""
    if account["role"] in PLATFORM_ROLES:
        return True
    _ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT 1 FROM company_accounts WHERE account_id = :account_id AND company_id = :company_id"
            ),
            {"account_id": account["id"], "company_id": company_id},
        ).fetchone()
    return row is not None


def _row_to_company(row) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "mcp_url": row.mcp_url,
        "welcome_message": row.welcome_message,
        "quick_replies": json.loads(row.quick_replies) if row.quick_replies else None,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def create_company(
    name: str, mcp_url: Optional[str], welcome_message: Optional[str] = None,
    quick_replies: Optional[list[str]] = None,
) -> dict:
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text(
                """
                INSERT INTO companies (name, mcp_url, welcome_message, quick_replies)
                VALUES (:name, :mcp_url, :welcome_message, :quick_replies)
                RETURNING id, name, mcp_url, welcome_message, quick_replies, created_at
                """
            ),
            {
                "name": name, "mcp_url": mcp_url, "welcome_message": welcome_message,
                "quick_replies": json.dumps(quick_replies) if quick_replies is not None else None,
            },
        ).fetchone()
    return _row_to_company(row)


def update_company(
    company_id: str, name: Optional[str], mcp_url: Optional[str], welcome_message: Optional[str] = None,
    quick_replies: Optional[list[str]] = None,
) -> Optional[dict]:
    """
    只更新有帶值的欄位（None 代表「這次沒有要改這個欄位」，不是「要清空」）——
    公司資訊頁面可能只改名稱、只改 mcp_url、只改 welcome_message／quick_replies，或同時改，
    呼叫端不用先查目前值再整包送回來。quick_replies 是清單，先序列化成 JSON 字串再跟其他
    欄位一樣用 COALESCE 判斷「這次有沒有要改」。
    """
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text(
                """
                UPDATE companies
                SET name = COALESCE(:name, name),
                    mcp_url = COALESCE(:mcp_url, mcp_url),
                    welcome_message = COALESCE(:welcome_message, welcome_message),
                    quick_replies = COALESCE(:quick_replies, quick_replies)
                WHERE id = :id
                RETURNING id, name, mcp_url, welcome_message, quick_replies, created_at
                """
            ),
            {
                "id": company_id, "name": name, "mcp_url": mcp_url, "welcome_message": welcome_message,
                "quick_replies": json.dumps(quick_replies) if quick_replies is not None else None,
            },
        ).fetchone()
    return _row_to_company(row) if row is not None else None


def get_company(company_id: str) -> Optional[dict]:
    _ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT id, name, mcp_url, welcome_message, quick_replies, created_at "
                "FROM companies WHERE id = :id"
            ),
            {"id": company_id},
        ).fetchone()
    return _row_to_company(row) if row is not None else None


def delete_company(company_id: str) -> bool:
    """
    硬刪除公司：company_accounts 靠 ON DELETE CASCADE 自動清掉綁定紀錄；RAG 文件/向量
    不是外鍵關聯（documents_store 的 kb_documents.company_id 沒有實體 FK，避免兩個模組
    互相依賴對方的 schema），呼叫端要自己另外呼叫 documents_store.purge_company()。
    """
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text("DELETE FROM companies WHERE id = :id RETURNING id"), {"id": company_id}
        ).fetchone()
    return row is not None


def list_companies_visible_to(account: dict) -> list[dict]:
    """platform 角色回全部；tenant 角色經 company_accounts join 回自己綁定的。"""
    _ensure_schema()
    engine = get_engine()
    if account["role"] in PLATFORM_ROLES:
        sql = sql_text(
            "SELECT id, name, mcp_url, welcome_message, quick_replies, created_at "
            "FROM companies ORDER BY created_at"
        )
        params = {}
    else:
        sql = sql_text(
            """
            SELECT c.id, c.name, c.mcp_url, c.welcome_message, c.quick_replies, c.created_at
            FROM companies c
            JOIN company_accounts ca ON ca.company_id = c.id
            WHERE ca.account_id = :account_id
            ORDER BY c.created_at
            """
        )
        params = {"account_id": account["id"]}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_company(r) for r in rows]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(account_id: str) -> str:
    """建立一個新 session，回傳明文 token 給呼叫端（僅此一次，DB 只存 hash）。"""
    _ensure_schema()
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_TTL_HOURS)
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                "INSERT INTO sessions (token_hash, account_id, expires_at) VALUES (:h, :account_id, :exp)"
            ),
            {"h": token_hash, "account_id": account_id, "exp": expires_at},
        )
    return token


def get_account_by_session(token: str) -> Optional[dict]:
    """雜湊比對 + 檢查 expires_at；查無或已過期一律回 None（呼叫端統一回 401，不用分辨原因，
    避免洩漏「token 格式對但過期了」這種細節給攻擊者）。"""
    _ensure_schema()
    token_hash = _hash_token(token)
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sql_text(
                """
                SELECT a.id, a.email, a.role, a.created_by, a.created_at
                FROM sessions s JOIN accounts a ON a.id = s.account_id
                WHERE s.token_hash = :h AND s.expires_at > now()
                """
            ),
            {"h": token_hash},
        ).fetchone()
    return _row_to_account(row) if row is not None else None


def revoke_session(token: str) -> None:
    _ensure_schema()
    token_hash = _hash_token(token)
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM sessions WHERE token_hash = :h"), {"h": token_hash})


def record_audit(
    actor_account_id: Optional[str], action: str, target_type: str, target_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """稽核紀錄：誰（actor_account_id）對什麼（target_type/target_id）做了什麼（action）。
    detail 是自由格式的補充資訊（例如上傳文件的路徑），存 JSONB。"""
    _ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                """
                INSERT INTO audit_log (actor_account_id, action, target_type, target_id, detail)
                VALUES (:actor_account_id, :action, :target_type, :target_id, :detail)
                """
            ),
            {
                "actor_account_id": actor_account_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "detail": _to_jsonb(detail),
            },
        )


def _to_jsonb(detail: Optional[dict]):
    import json

    return json.dumps(detail) if detail is not None else None


def _row_to_audit_entry(row) -> dict:
    return {
        "id": row.id,
        "actor_email": row.actor_email,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "detail": row.detail,
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
    }


def list_audit_log_for_company(company_id: str, limit: int = 100) -> list[dict]:
    """
    查一家公司相關的稽核紀錄：target_type='company' 時 target_id 本身就是 company_id；
    'kb_document' 跟部分 'account' 動作（新增/刪除次帳號）則是把 company_id 存在 detail
    這個 JSONB 欄位裡（見 main.py 各個 record_audit() 呼叫點），所以兩種都要比對，才不會漏掉
    「新增/刪除這家公司的協作帳號」這類紀錄。
    """
    _ensure_schema()
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(
                """
                SELECT al.id, a.email AS actor_email, al.action, al.target_type, al.target_id,
                       al.detail, al.created_at
                FROM audit_log al
                LEFT JOIN accounts a ON a.id = al.actor_account_id
                WHERE al.target_id = :company_id OR al.detail->>'company_id' = :company_id
                ORDER BY al.created_at DESC
                LIMIT :limit
                """
            ),
            {"company_id": company_id, "limit": limit},
        ).fetchall()
    return [_row_to_audit_entry(r) for r in rows]


def bootstrap_initial_platform_admins() -> None:
    """
    解決「雞生蛋」的 bootstrap 問題：一開始 accounts 表沒有任何帳號，沒人能登入。
    只在 accounts 表完全是空的時候，把 settings.INITIAL_PLATFORM_ADMIN_EMAILS 列出的
    email 建成 platform_primary；一次性、冪等（表有資料後就不會再跑）。
    這個函式由 _ensure_schema() 在確認 schema 建立完成後自動呼叫，不需要呼叫端另外處理。
    """
    if not settings.INITIAL_PLATFORM_ADMIN_EMAILS:
        return
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(sql_text("SELECT count(*) FROM accounts")).scalar_one()
    if count > 0:
        return
    for email in settings.INITIAL_PLATFORM_ADMIN_EMAILS:
        with engine.begin() as conn:
            conn.execute(
                sql_text(
                    """
                    INSERT INTO accounts (email, role, created_by) VALUES (:email, 'platform_primary', NULL)
                    ON CONFLICT (email) DO NOTHING
                    """
                ),
                {"email": email},
            )
