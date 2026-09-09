"""
專案設定值。讀取 .env（沒有的話用預設值），對應：
- EMBEDDING_MODEL_NAME / LLM_MODEL_NAME: 對應提案中「Embedding 模型」與「生成模型」的技術選型
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()


def _has_gemini_key() -> bool:
    """判斷是否有可用的 Gemini API key，用來在未明確指定 RAG_ENGINE 時自動選擇引擎。"""
    if os.getenv("GEMINI_API_KEY"):
        return True
    llm_keys_path = os.getenv("LLM_KEYS_PATH", "./llm_keys.json")
    try:
        if os.path.exists(llm_keys_path):
            with open(llm_keys_path, encoding="utf-8") as f:
                if json.load(f).get("google", {}).get("api_key"):
                    return True
    except Exception:
        pass
    return False


class Settings:
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    LLM_MODEL_NAME: str = "openbmb/MiniCPM5-2B"

    TOP_K: int = 3

    # Chroma 向量資料庫持久化目錄；正式上線建議指向獨立磁碟路徑並定期備份
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    # 對話紀錄 SQLite 檔案路徑，供未來「管理者摘要當日提問」功能使用
    CHAT_LOG_DB_PATH: str = os.getenv("CHAT_LOG_DB_PATH", "./chat_log.db")

    # 訂單資料 SQLite 檔案路徑；MCP 查不到 corp-backend 時的 fallback 資料來源
    ORDERS_DB_PATH: str = os.getenv("ORDERS_DB_PATH", "./orders.db")

    # corp-backend 的 MCP Streamable HTTP endpoint，訂單查詢的真正資料來源（見 app/orders.py）
    CORP_BACKEND_MCP_URL: str = os.getenv("CORP_BACKEND_MCP_URL", "http://localhost:8001/mcp")

    # 多輪對話最多保留幾輪（一輪 = 一則使用者訊息 + 一則機器人回覆），避免 context 太長讓本地小模型變慢
    MAX_HISTORY_TURNS: int = 4

    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    # 線上付費 LLM 的 API key／模型名稱設定檔（不進 git，範本見 llm_keys.example.json）
    LLM_KEYS_PATH: str = os.getenv("LLM_KEYS_PATH", "./llm_keys.json")

    # RAG 檢索引擎："custom"（自訂 Chroma + 手寫檢索）、"llamaindex"（本地 LlamaIndex embedding）
    # 或 "gemini"/"online"（線上 Gemini embedding）。
    # 未明確設定 RAG_ENGINE 時自動判斷：偵測到 Gemini API key（GCP 部署會設定）就用 gemini，
    # 沒有 key（例如本機開發未設定）則退回 llamaindex，避免因缺 key 導致服務起不來。
    # 兩套引擎介面相同，見 app/rag/engine.py；語意拆分規則兩套共用（app/rag/product_parser.py）。
    RAG_ENGINE: str = os.getenv("RAG_ENGINE") or ("gemini" if _has_gemini_key() else "llamaindex")

    # Online 引擎的索引持久化目錄；llamaindex 引擎改用 pgvector（見下方 RAG_PG_*），不再用本地磁碟 persist
    CHROMA_ONLINE_PERSIST_DIR: str = os.getenv("CHROMA_ONLINE_PERSIST_DIR", "./chroma_online_data")

    # llamaindex 引擎的 pgvector（PostgreSQL）連線設定；本機開發指向 docker 起的 pgvector，
    # 正式環境改指向 Cloud SQL for PostgreSQL（本次不處理 Cloud SQL 建置，只確保連線設定可切換）
    RAG_PG_HOST: str = os.getenv("RAG_PG_HOST", "localhost")
    RAG_PG_PORT: int = int(os.getenv("RAG_PG_PORT", "5432"))
    RAG_PG_DATABASE: str = os.getenv("RAG_PG_DATABASE", "rag")
    RAG_PG_USER: str = os.getenv("RAG_PG_USER", "postgres")
    RAG_PG_PASSWORD: str = os.getenv("RAG_PG_PASSWORD", "postgres")
    RAG_PG_TABLE: str = os.getenv("RAG_PG_TABLE", "kb_chunks")

    # 檢索引擎的「有沒有查到答案」距離門檻分開設定，因為分數尺度不同、不能共用同一個數字
    RAG_NO_INFO_THRESHOLDS: dict = {"llamaindex": 0.30, "online": 0.90, "gemini": 0.90}


settings = Settings()
