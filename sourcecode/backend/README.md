# Backend — 智慧CRM系統 API

FastAPI 服務，提供 `/api/chat`，對應提案 #1（產品問答 RAG）與 #2（訂單查詢），
另外有管理者用的 `/api/admin/summary`（當日提問摘要）跟 `/api/providers`（可用 LLM 清單）。

## 環境需求

- Python 3.10+
- 本地 LLM（provider=local）固定用 **MLX + `mlx-community/Qwen3.5-2B-4bit`**（模型名稱可用
  `.env` 的 `MLX_LLM_MODEL_NAME` 覆蓋），**只支援 Apple Silicon（M 系列晶片）Mac**，吃 Mac 的
  Metal GPU 加速；需要額外安裝 `requirements-mlx.txt`（`pip install -r requirements-mlx.txt`）。
  `app/llm.py` 預設用 `enable_thinking=False` 關掉內部思考過程直接回答，輸出偶爾還是簡體字，
  `generate()` 會自動做簡轉繁（台灣用語）後處理。
  **在非 Apple Silicon 機器上（包含正式環境 Cloud Run）呼叫 provider=local 會直接回錯誤**——
  正式環境固定用線上 provider，不提供本地 LLM 這個選項；本機開發如果不是 Apple Silicon，也只能
  選線上 provider。
  （原本用的 openbmb/MiniCPM5-2B 已經拿掉：一來它在 Apple Silicon 的 MPS 上會直接當機
  segfault，二來它要求的 `transformers>=5.6` 會跟其他想接的套件版本衝突。）
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
| `local`（預設） | 本地 Qwen3.5-2B（MLX） | 不需要 API key、免費，但僅限 Apple Silicon 開發機 |
| `anthropic` | Claude | `llm_keys.json` 填 `anthropic.api_key` |
| `openai` | GPT | `llm_keys.json` 填 `openai.api_key` |
| `google` | Gemini | `llm_keys.json` 填 `google.api_key` |
| `xai` | Grok | `llm_keys.json` 填 `xai.api_key` |

`llm_keys.json` 不會進 git（已加進 `.gitignore`），每個人要自己填自己的 key。
沒填 key 的 provider 選了會友善回覆「尚未設定 API key」，不會讓服務掛掉；
`GET /api/providers` 可以查詢目前有哪些 provider 已經設定好 key。

## RAG 引擎

檢索固定用 `llamaindex` 引擎：LlamaIndex 的 `VectorStoreIndex` + **pgvector（PostgreSQL）**
做索引與檢索（本地 embedding），需要另外安裝 `requirements-local-llm.txt`。支援單一文件的
新增/刪除/更新（見下方「知識庫文件管理」），不用整批重建索引。

本地 embedding 模型用哪個實作由 `.env` 的 `EMBEDDING_BACKEND` 決定：
- `onnx_int8`（預設）：`app/rag/onnx_embedding.py` 直接用 `onnxruntime` 跑 int8 量化版
  `multilingual-e5-base`（`Teradata/multilingual-e5-base` 這個 repo 轉換的），檔案小、
  記憶體佔用低，繞過官方的 `optimum` 整合套件（跟 `mlx-lm` 等套件要求的 `transformers`
  版本硬衝突，無解）。
- `huggingface`：原本的 fp32 `HuggingFaceEmbedding`，int8 版本有問題時可以切回這個，
  不用改程式碼，`.env` 設 `EMBEDDING_BACKEND=huggingface` 即可。

（原本還有兩套：自製的 `custom` 引擎——Chroma + 手寫檢索，已隨 `llamaindex` 引擎改用
pgvector 一起退休；線上 Gemini embedding + Chroma 的 `gemini`/`online` 引擎也已移除，
embedding 統一改用本地 llamaindex，不再依賴線上 embedding API。線上 `google` provider
目前只用在 LLM 回答，見上方「切換回答模型」。）

知識庫檔案都在 `app/data/`：`products_20_quirky.md`（20 項產品文案，用 `product_parser.py` 拆分）
與 `warranty_policy.md` / `return_policy.md` / `shipping_payment.md` / `faq.md`（保固、退換貨、運送
付款、常見問題，用 `policy_parser.py` 依 markdown 標題拆分）。這些檔案只在 pgvector table 是空的
時候（例如第一次接上新資料庫）由 `app/rag/documents_store.py` 的 `seed_if_empty()` 自動灌入一次，
之後要新增/刪除/更新內容改走 `/api/admin/documents` 系列 API，不用再手動改檔案或清資料重建索引。

### pgvector（Supabase）

`llamaindex` 引擎需要一個有裝 pgvector extension 的 PostgreSQL。本機開發與 Cloud Run 正式
環境統一指向同一個 Supabase 專案的 **Transaction pooler**（Cloud Run 這種無伺服器環境的
建議用法），不再各自起一個 pgvector：

```
RAG_PG_HOST=aws-0-ap-northeast-2.pooler.supabase.com
RAG_PG_PORT=6543
RAG_PG_DATABASE=postgres
RAG_PG_USER=postgres.<你的 Supabase 專案 ref>
RAG_PG_PASSWORD=<專案建立時設定的資料庫密碼，不要外流／提交進版控>
RAG_PG_TABLE=kb_chunks
```

Supabase 專案預設就有 `vector` extension 可用；`PGVectorStore.from_params()` 預設
`perform_setup=True`，第一次寫入時會自動建立資料表（實體資料表名稱是
`data_<RAG_PG_TABLE>`，例如 `data_kb_chunks`，不是 `RAG_PG_TABLE` 本身），不用手動建 schema。

也可以改指向本機自己起的 PostgreSQL（例如 `docker run -d -e POSTGRES_PASSWORD=postgres
-p 5432:5432 pgvector/pgvector:pg16`），只要裝了 `vector` extension、把 `RAG_PG_*` 指過去
即可，不需要改程式碼。

## 知識庫文件管理

下列 API 依賴 llamaindex 引擎的 pgvector 索引（唯一支援的引擎）。
新增/更新是上傳 `.md` 檔（`multipart/form-data`），不是 JSON body；**目前只支援 `.md`**，
其他副檔名或非 UTF-8 編碼一律回 400：

| Method | Path | 說明 |
|---|---|---|
| `GET` | `/api/admin/documents` | 列出所有文件（`doc_id`/`category`/`chunk_count`/`uploaded_at`/`file_size_bytes`） |
| `POST` | `/api/admin/documents` | 上傳新文件（multipart：`file` + `category` 欄位），`doc_id` 直接沿用檔名，已存在回 409 |
| `PUT` | `/api/admin/documents/{doc_id}` | 上傳新版檔案覆蓋內容（multipart：`file` 欄位，分類沿用既有值），查無文件回 404 |
| `DELETE` | `/api/admin/documents/{doc_id}` | 刪除文件（該 `doc_id` 底下所有 chunk），查無文件回 404 |

「更新」會先比對 SHA256（`content_hash`）：內容跟既有版本一樣就跳過刪除+重新 embed，回應
`content_changed: false`；有變才刪除該文件舊 chunk、依 `category` 對應的 parser 重新解析插入
新 chunk（`content_changed: true`）。不另外保存文件原文，pgvector 的 chunk 表（文字 + 向量 +
metadata，含 `content_hash`/`uploaded_at`/`file_size_bytes`）就是唯一資料來源。

新增或更新時若偵測到**其他** `doc_id` 存了完全一樣的內容（`content_hash` 相同），回應會帶
`duplicate_of: "<那個 doc_id>"` 提示管理者，但不會擋下這次上傳/更新。

## 注意事項

- 第一次啟動會需要下載 Embedding 模型與本地 LLM 模型，依網路速度可能需要數分鐘到數十分鐘
- 向量資料存在 pgvector（PostgreSQL），服務重啟不需要重新 embed
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
