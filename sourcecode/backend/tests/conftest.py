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
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_tmp_dir = tempfile.mkdtemp(prefix="crm_backend_test_")
os.environ["CHAT_LOG_DB_PATH"] = str(Path(_tmp_dir) / "chat_log_test.db")

os.chdir(BACKEND_DIR)

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
