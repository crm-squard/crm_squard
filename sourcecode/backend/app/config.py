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

    # MCP（訊息以 @mcp 開頭時，LLM 透過公司的 mcp_url 呼叫 tool，見 app/mcp_client.py）
    # 單次 MCP 請求的逾時秒數，避免公司的 MCP server 太慢拖住整個聊天請求
    MCP_TIMEOUT_SECONDS: float = float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))
    # tool 回傳內容交給 LLM 前的字數上限，避免一個 tool 回傳整批資料塞爆 context
    MCP_TOOL_RESULT_MAX_CHARS: int = int(os.getenv("MCP_TOOL_RESULT_MAX_CHARS", "4000"))
    # 聊天使用者輸入的文字會影響 LLM 選 tool（prompt injection），預設只讓 LLM 看到「非寫入型」tool；
    # 公司的 MCP server 明確要提供寫入型 tool 給聊天使用時才打開，見 mcp_client._is_exposed_to_llm()
    MCP_ALLOW_WRITE_TOOLS: bool = os.getenv("MCP_ALLOW_WRITE_TOOLS", "false").lower() == "true"
    # 一次 @mcp 對話，LLM 最多連續呼叫 tool 幾輪，超過就直接要求它用現有資訊回答
    MCP_MAX_TOOL_ROUNDS: int = int(os.getenv("MCP_MAX_TOOL_ROUNDS", "3"))

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

    # 多租戶帳號（Google 登入）：前端拿到的 Google ID token 要用這個 OAuth Client ID 驗證
    # 簽發對象，避免拿到別的應用程式簽的 token 也被接受。Phase 1 還沒有前端串接，這裡先
    # 留設定值供 app/auth.py 使用，本機測試靠 monkeypatch 繞過真的驗證。
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # session token 有效期限（小時），過期後 accounts_store.get_account_by_session() 視同查無此帳號。
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "24"))

    # 開發用「一鍵登入」（見 main.py 的 /api/auth/dev-login），預設關閉。
    # 警告：本機開發用的資料庫可能就是正式環境那一個，開啟後登入會在該資料庫建立／使用一個
    # platform 管理員帳號。因此：預設關閉；只接受本機（loopback）請求；在 Cloud Run 上（有
    # K_SERVICE 環境變數）即使設成 true 也一律停用；且只會「自動建立」保留網域（.invalid／
    # .local／.test／.localhost）的帳號——這種位址不可能通過 Google 登入，不會被別人冒用。
    # 想用真實 email 登入時，該帳號必須已經存在，這個端點不會替真實 email 建立管理員帳號。
    DEV_LOGIN_ENABLED: bool = os.getenv("DEV_LOGIN_ENABLED", "false").lower() == "true"
    DEV_LOGIN_EMAIL: str = os.getenv("DEV_LOGIN_EMAIL", "dev-admin@local.invalid")

    # 服務啟動時，若 accounts 表是空的（例如全新資料庫，還沒有人能登入），把這裡列出的
    # email（逗號分隔）建成 platform_primary 帳號，解決「雞生蛋」的 bootstrap 問題。
    INITIAL_PLATFORM_ADMIN_EMAILS: list = [
        email.strip()
        for email in os.getenv("INITIAL_PLATFORM_ADMIN_EMAILS", "").split(",")
        if email.strip()
    ]


settings = Settings()
