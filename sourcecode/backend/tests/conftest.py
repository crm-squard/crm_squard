"""
測試共用設定。

兩個重點：
1. 把 backend 目錄加進 sys.path 並 chdir 過去，讓 `import app...` 跟 orders.db／
   chat_log.db 這類相對路徑的行為，跟 `run_dev.sh`（cd 進 backend 再啟動）一致，
   不管實際從哪個目錄執行 pytest 都一樣。
2. 在任何測試 import app.config / app.main 之前，把 CHAT_LOG_DB_PATH 指到暫存檔，
   避免 /api/chat 測試把對話紀錄寫進共用的 chat_log.db。

注意：orders.db 沒有另外導向暫存檔——訂單查詢的測試直接讀現有 orders.db 的範例資料
（見 SEED_ORDERS），因為查詢路徑全程只有 SELECT、不會寫入，不會污染這份共用檔案。
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_tmp_dir = tempfile.mkdtemp(prefix="crm_backend_test_")
os.environ["CHAT_LOG_DB_PATH"] = str(Path(_tmp_dir) / "chat_log_test.db")

os.chdir(BACKEND_DIR)

# 多租戶帳號測試共用 helper：直接透過 accounts_store 建帳號/session（不透過真的 Google
# 登入流程——pytest 沒辦法真的拿到一個有效的 Google ID token，Google 驗證本身用
# monkeypatch app.auth.verify_google_id_token 在 test_auth.py 個別測試），
# 跟 documents_api／companies／accounts 測試共用同一套 fixture，統一在這裡定義避免重複。


def _unique_email(prefix: str = "pytest") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def platform_account():
    """建立一個 platform_primary 帳號，測試結束後刪除（連帶清掉 session，見 accounts_store）。"""
    from app import accounts_store

    account = accounts_store.create_account(_unique_email("platform"), "platform_primary", None)
    yield account
    accounts_store.delete_account(account["id"])


@pytest.fixture
def platform_token(platform_account):
    """platform_account 的登入 session token，供 Authorization: Bearer 使用。"""
    from app import accounts_store

    return accounts_store.create_session(platform_account["id"])


@pytest.fixture
def test_company(request):
    """
    建立一家測試用公司，測試結束後硬刪除（含清掉該公司的 RAG 文件記錄與向量 chunk）。

    支援用 @pytest.mark.parametrize 或 indirect fixture 的方式帶入 mcp_url（見
    test_orders.py／test_chat_api.py 的訂單查詢測試，需要一家「有設定 mcp_url」的公司）；
    沒有額外參數時預設 mcp_url=None，對應「公司沒開訂單查詢功能」的情境。
    """
    from app import accounts_store
    from app.rag.documents_store import purge_company
    from app.rag.engine import get_retriever

    mcp_url = getattr(request, "param", None)
    company = accounts_store.create_company(f"Pytest Company {uuid.uuid4().hex[:8]}", mcp_url)
    yield company
    accounts_store.delete_company(company["id"])
    try:
        purge_company(company["id"], get_retriever().index)
    except Exception:
        pass

# 對應 app/orders.py 的 _SEED_ORDERS，orders.db 啟動時已灌入這 5 筆範例資料，
# 供各測試檔直接引用，避免每個檔案各自重複硬編碼一份。
SEED_ORDERS = {
    "A12345": {"status": 2, "eta": "8月28日", "items": "智慧掃地機器人 R5 Pro ×1"},
    "B98231": {"status": 0, "eta": "9月5日", "items": "智慧冷氣 A8（1.5噸）×1"},
    "C55210": {"status": 3, "eta": "已送達", "items": "智慧電視 V6 55吋 ×1"},
    "D77102": {"status": 1, "eta": "9月8日", "items": "智慧掃地機器人 R5 Pro ×2、智慧電視 V6 43吋 ×1"},
    "E30044": {"status": 2, "eta": "9月4日", "items": "智慧冷氣 A8（2.2噸）×1"},
}

# 保證不存在於 orders.db 的訂單編號，符合 [A-Za-z]\d{5} 格式，用來測查無此訂單的路徑。
NON_EXISTENT_ORDER_CODE = "Z99999"
