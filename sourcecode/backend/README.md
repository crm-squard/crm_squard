# Backend — 智慧CRM系統 API

FastAPI 服務，提供 `/api/chat`，對應提案 #1（產品問答 RAG）與 #2（訂單查詢），
另外有管理者用的 `/api/admin/summary`（當日提問摘要）跟 `/api/providers`（可用 LLM 清單）。

## 環境需求

- Python 3.10+
- 本地 LLM（provider=local）固定使用 openbmb/MiniCPM5-2B，CPU 也可執行（速度較慢），不需要 bitsandbytes/GPU。
  這顆是「混合推理」模型，`app/llm.py` 預設用 `enable_thinking=False` 關掉內部思考過程直接回答，
  但輸出仍常是簡體字，`generate()` 會自動做簡轉繁（台灣用語）後處理。
  **注意：這顆模型在 Apple Silicon 的 MPS 上會直接當機（segfault），`app/llm.py` 已經刻意跳過
  MPS、強制用 CPU 跑**（在 M3 Pro 上單次回應約 20-30 秒；之後若要用其他本地模型要重新驗證 MPS）
- 或完全不跑本地模型，改用線上付費 API（見下方「切換回答模型」）

## 啟動步驟

```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
cp llm_keys.example.json llm_keys.json
# 需要的話編輯 .env / llm_keys.json，見下面兩節說明

uvicorn app.main:app --reload --port 8000
```

啟動後可用瀏覽器打開 http://localhost:8000/health 確認服務正常。服務啟動時會自動預載
Embedding 與本地 LLM 模型（第一次啟動會需要下載，依網路速度可能要數分鐘到數十分鐘）。

## 切換回答模型

`/api/chat` 的 `provider` 欄位決定用哪個 LLM 回答（前端聊天視窗有下拉選單可以選）：

| provider | 說明 | 需要什麼 |
|---|---|---|
| `local`（預設） | 本地 openbmb/MiniCPM5-2B | 不需要 API key，免費但速度較慢 |
| `anthropic` | Claude | `llm_keys.json` 填 `anthropic.api_key` |
| `openai` | GPT | `llm_keys.json` 填 `openai.api_key` |
| `google` | Gemini | `llm_keys.json` 填 `google.api_key` |
| `xai` | Grok | `llm_keys.json` 填 `xai.api_key` |

`llm_keys.json` 不會進 git（已加進 `.gitignore`），每個人要自己填自己的 key。
沒填 key 的 provider 選了會友善回覆「尚未設定 API key」，不會讓服務掛掉；
`GET /api/providers` 可以查詢目前有哪些 provider 已經設定好 key。

## RAG 引擎切換

`.env` 的 `RAG_ENGINE` 決定檢索用哪套實作，功能等價、介面相同，可以隨時切換：

- `llamaindex`：LlamaIndex 的 `VectorStoreIndex` + **pgvector（PostgreSQL）**做索引與檢索（本地 embedding）。
  支援單一文件的新增/刪除/更新（見下方「知識庫文件管理」），不用整批重建索引。
- `gemini`（或 `online`）：改用線上 Gemini API 做 embedding，不需要 `torch` / `sentence-transformers`

（原本還有一套自製的 `custom` 引擎——Chroma + 手寫檢索，已隨 `llamaindex` 引擎改用 pgvector
一起退休。）

**不設定 `RAG_ENGINE` 時會自動判斷**（見 `app/config.py` 的 `_has_gemini_key()`）：偵測到
`GEMINI_API_KEY`（環境變數或 `llm_keys.json` 的 `google.api_key`）就自動用 `gemini`，沒有 key
就退回 `llamaindex`。本機開發通常不會特別設 `GEMINI_API_KEY`，所以預設會走 `llamaindex`（需要
額外安裝 `requirements-local-llm.txt`）；GCP 部署會設定 `GEMINI_API_KEY`，所以會自動走 `gemini`，
不需要另外設定 `RAG_ENGINE`。要強制指定某一套，就在 `.env` 明確寫上 `RAG_ENGINE=llamaindex` 等值覆蓋。

兩套引擎共用同一套語意拆分規則（`app/rag/product_parser.py` / `app/rag/policy_parser.py`），差別
只在「怎麼建索引、怎麼查」，所以檢索結果品質應該接近，但各自的距離分數尺度不同，`app/config.py` 的
`RAG_NO_INFO_THRESHOLDS` 分開設定「查無資訊」的判斷門檻。

知識庫檔案都在 `app/data/`：`products_20_quirky.md`（20 項產品文案，用 `product_parser.py` 拆分）
與 `warranty_policy.md` / `return_policy.md` / `shipping_payment.md` / `faq.md`（保固、退換貨、運送
付款、常見問題，用 `policy_parser.py` 依 markdown 標題拆分）。這些檔案只在 pgvector table 是空的
時候（例如第一次接上新資料庫）由 `app/rag/documents_store.py` 的 `seed_if_empty()` 自動灌入一次，
之後要新增/刪除/更新內容改走 `/api/admin/documents` 系列 API，不用再手動改檔案或清資料重建索引。

### 本機開發：啟動 pgvector

`llamaindex` 引擎需要一個有裝 pgvector extension 的 PostgreSQL，本機開發用 Docker 起一個即可：

```bash
docker run -d --name rag-pgvector -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg16
docker exec rag-pgvector psql -U postgres -c "CREATE DATABASE rag;"
docker exec rag-pgvector psql -U postgres -d rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

再到 `.env` 設定對應的連線資訊（預設值就是對應上面這個 docker 指令，通常不用改）：

```
RAG_PG_HOST=localhost
RAG_PG_PORT=5432
RAG_PG_DATABASE=rag
RAG_PG_USER=postgres
RAG_PG_PASSWORD=postgres
RAG_PG_TABLE=kb_chunks
```

`PGVectorStore.from_params()` 預設 `perform_setup=True`，第一次寫入時會自動建立資料表
（實體資料表名稱是 `data_<RAG_PG_TABLE>`，例如 `data_kb_chunks`，不是 `RAG_PG_TABLE` 本身），
不用手動建 schema。正式環境改指向 Cloud SQL for PostgreSQL 即可（本次不處理 Cloud SQL 建置）。

## 知識庫文件管理

只有 `RAG_ENGINE=llamaindex` 支援下列 API（其他引擎目前沒有增量更新機制，呼叫會回 400）：

| Method | Path | 說明 |
|---|---|---|
| `GET` | `/api/admin/documents` | 列出所有文件（`doc_id`/`category`/`chunk_count`） |
| `POST` | `/api/admin/documents` | 新增文件（body: `source`/`category`/`content`），`doc_id` 已存在回 409 |
| `PUT` | `/api/admin/documents/{doc_id}` | 更新內容（body 只需 `content`，分類沿用既有值），查無文件回 404 |
| `DELETE` | `/api/admin/documents/{doc_id}` | 刪除文件（該 `doc_id` 底下所有 chunk），查無文件回 404 |

「更新」= 刪除該文件舊 chunk + 依 `category` 對應的 parser 重新解析、插入新 chunk，不做差異比對，
不另外保存文件原文（pgvector 的 chunk 表就是唯一資料來源）。

## 注意事項

- 第一次啟動會需要下載 Embedding 模型與本地 LLM 模型，依網路速度可能需要數分鐘到數十分鐘
- `llamaindex` 引擎的向量資料改存在 pgvector（PostgreSQL），服務重啟不需要重新 embed；
  `online`/`gemini` 引擎仍用本地磁碟 persist（`chroma_online_data/`）
- `/api/admin/summary`、`/api/admin/documents` 系列目前都沒有任何身分驗證，正式上線前必須加上
  管理者登入/權限檢查

## API

### `POST /api/chat`

```json
// request
{
  "message": "無線滑鼠支援多少 DPI？",
  "history": [],
  "provider": "local"
}

// response（產品問題）
{ "type": "product", "text": "...", "source": "Wireless Mouse（無線滑鼠）", "sources": [...] }

// response（訂單查詢）
{ "type": "order", "code": "A12345", "status": 2, "eta": "8月28日", "items": "..." }
```

### `GET /api/providers`

回傳可選的 LLM 清單與是否已設定 key，供前端畫下拉選單用。

### `GET /api/admin/summary?date=YYYY-MM-DD`

回傳指定日期（預設今天，UTC）使用者提問的主題摘要，`date` 省略時查今天。
