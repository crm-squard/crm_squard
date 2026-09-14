"""
專案設定值。讀取 .env（沒有的話用預設值），對應：
- EMBEDDING_MODEL_NAME / MLX_LLM_MODEL_NAME: 對應提案中「Embedding 模型」與「生成模型」的技術選型
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    # "onnx_int8"（預設）：繞過 optimum，用 onnxruntime 跑 int8 量化版本，檔案小、記憶體佔用低
    # （見 app/rag/onnx_embedding.py）；"huggingface"：原本的 fp32 HuggingFaceEmbedding，
    # 遇到 int8 版本有問題時可以用這個切回去，不用改程式碼。
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "onnx_int8")
    # provider=local 固定用這顆，只能在 Apple Silicon（MLX）上跑，見 app/llm.py 的說明；
    # 正式環境（Cloud Run）固定用線上 provider，不會用到這個設定值。
    MLX_LLM_MODEL_NAME: str = os.getenv("MLX_LLM_MODEL_NAME", "mlx-community/Qwen3.5-2B-4bit")

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

    # llamaindex 引擎的 pgvector（PostgreSQL）連線設定；本機開發指向 docker 起的 pgvector，
    # 正式環境改指向 Cloud SQL for PostgreSQL（本次不處理 Cloud SQL 建置，只確保連線設定可切換）
    RAG_PG_HOST: str = os.getenv("RAG_PG_HOST", "localhost")
    RAG_PG_PORT: int = int(os.getenv("RAG_PG_PORT", "5432"))
    RAG_PG_DATABASE: str = os.getenv("RAG_PG_DATABASE", "rag")
    RAG_PG_USER: str = os.getenv("RAG_PG_USER", "postgres")
    RAG_PG_PASSWORD: str = os.getenv("RAG_PG_PASSWORD", "postgres")
    RAG_PG_TABLE: str = os.getenv("RAG_PG_TABLE", "kb_chunks")

    # llamaindex 引擎「有沒有查到答案」的距離門檻（1 - 相似度分數），只在 provider=local 時
    # 用來判斷要不要跳過 LLM 直接回「查無此資訊」，見 app/agent.py 的說明。
    RAG_NO_INFO_THRESHOLD: float = 0.30


settings = Settings()
