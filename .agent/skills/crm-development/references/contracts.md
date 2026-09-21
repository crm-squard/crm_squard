# CRM 介面契約

修改 API 或前後端資料流時讀取本文件。實際型別來源為 `sourcecode/backend/app/schemas.py`，FastAPI 產生的 OpenAPI schema 可作為機器可讀契約。

## `POST /api/chat`

Widget 呼叫時必須帶入企業客戶識別 Header：`X-Client-ID: <assigned-client-id>`。此值是公開識別碼，
目前只驗證必填及最長 128 字元，不代表登入或授權憑證。

請求：

```json
{
  "message": "無線滑鼠支援多少 DPI？",
  "history": [{ "role": "user", "content": "上一輪問題" }],
  "provider": "local"
}
```

- `message`：1 至 500 字元。
- `history`：最多 20 筆；`role` 僅能是 `user` 或 `assistant`，每筆 `content` 最多 2000 字元。
- `provider`：`local`、`anthropic`、`openai`、`google` 或 `xai`。

回應以 `type` 判別：

- `product`：包含 `text`，可包含 `source` 與 `sources`。
- `order`：包含 `code`、`status`、`eta` 與 `items`。**後端目前不會產生這個型別**（訂單專屬的分流已移除），保留在契約中是為了前端相容，之後若要用結構化卡片呈現 MCP 結果可再啟用。
- `text`：包含 `text`，用於提示、查無資料或可理解的錯誤訊息。

## `@mcp` 對話（透過公司 MCP server 回答）

`POST /api/chat` 的 `message` 以 `@mcp` 開頭（忽略大小寫與前置空白）時，不走 RAG，改把去掉 `@mcp` 之後的
問題，連同該公司 `mcp_url` 的 `tools/list` 交給 LLM，由 LLM 自己決定要不要呼叫、呼叫哪個 tool，最後
整理成文字。回應一律是 `type: text`。

- 支援 `provider: google`（Gemini）與 `provider: local`（本地 MLX 上的 Qwen，僅限 Apple Silicon 開發機）；其他 provider 會回提示文字。
  本地 2B 小模型選 tool 的準確度不如 Gemini：缺少必填參數時它會拿空字串呼叫 tool，所以呼叫前一律先檢查必填參數，
  缺少就回錯誤讓模型向顧客詢問；沒有合適 tool 的一般問題它可能憑印象回答（可能編造）。
- backend 不認識任何特定 tool（沒有寫死的名稱、參數或回傳欄位）：公司的 MCP server 新增 tool 後不需修改 backend。
- 協定使用 MCP 2026-07-28 無狀態模式：不做 `initialize` 握手、不帶 `Mcp-Session-Id`，每個請求自帶協定版本與
  client 資訊；每家公司使用自己的 Bearer 金鑰（`chatbots.mcp_token`）。
- 預設只會把「非寫入型」tool 交給 LLM（`annotations.destructive_hint` 為 true 或 `read_only_hint` 為 false 的會被隱藏，
  `MCP_ALLOW_WRITE_TOOLS=true` 才會放行）；聊天訊息是不受信任的輸入，權限邊界仍以 MCP server 端拆分與認證為準。
- LLM 最多連續呼叫 `MCP_MAX_TOOL_ROUNDS`（預設 3）輪 tool；tool 回傳內容超過 `MCP_TOOL_RESULT_MAX_CHARS`（預設 4000）字會被截斷。
- 所有失敗（沒有 `mcp_url`、provider 不支援、MCP server 連不上或金鑰無效、逾時）都回 `type: text` 的可理解訊息，
  不退回 RAG、不回 HTTP 5xx。
- 每次 LLM 呼叫的 tool 會寫入 `mcp_tool_log`（公司、tool 名稱、參數、是否失敗）；**不記 tool 回傳內容**，
  但參數可能含顧客資訊（例如訂單編號），目前沒有保留期限，需依隱私規範另行處理。
- 沒有 `@mcp` 前綴的訊息一律走 RAG + LLM，就算內容長得像訂單編號。

### 公司的 MCP 金鑰

- `POST /api/admin/chatbots`、`PUT /api/admin/chatbots/{chatbot_id}` 可帶 `mcp_token`；`PUT` 不帶代表不變更，
  空字串代表清除。
- 金鑰不會出現在 `ChatbotInfo`／列表／`/api/auth/me` 回應，這些回應只有布林值 `has_mcp_token`。
- `GET /api/admin/chatbots/{chatbot_id}/mcp-token`：回傳 `{ "mcp_token": "..." | null }`，權限同其他公司管理端點
  （platform 帳號或綁定該公司的帳號，否則 403），每次呼叫都會寫入稽核紀錄（`reveal_mcp_token`）。
  稽核紀錄只記「有沒有動到金鑰」，不記金鑰內容。金鑰目前以明文存在資料庫，因為必須能還原才能送給 MCP server。

## 其他端點

- `GET /health`：回傳 `{ "status": "ok" }`。
- `POST /api/warmup`：載入模型後回傳狀態。
- `GET /api/providers`：需帶 `X-Client-ID`，回傳 provider 的 `id`、`label` 與 `configured`。
- `GET /api/widget/config`：需帶 `X-Client-ID`，回傳 Widget 品牌名稱、歡迎訊息、Logo 與樣式 token；MVP 先回傳共用預設值。
- `GET /api/admin/summary?date=YYYY-MM-DD`：回傳 `date`、`question_count` 與 `summary`；此端點目前沒有身分驗證。

## `/api/admin/documents*`（知識庫文件管理，只支援 `RAG_ENGINE=llamaindex`）

目前沒有任何身分驗證，正式上線前必須加上管理者登入/權限檢查。

**doc_id 完全內部化，API 一律用「路徑」溝通**：後端用 `kb_documents`（`content_hash` 唯一，判斷
「是不是同一份內容」）＋ `kb_document_labels`（路徑/標籤，一個內容可以同時掛在多個路徑底下，一對多）
這兩張表管理身分，內部的流水號 `doc_id` 從不出現在 API 請求/回應裡；呼叫端只需要知道「路徑」。
`tags` 是自由標籤陣列，掛在路徑上（不是掛在內容上）——同一份內容掛兩個路徑，標籤可以各自不同。
帶斜線的路徑參數用 `{path:path}` 承接。

**新增/更新/改標籤/掛到既有內容，統一是 `PUT /api/admin/documents/{path}` 這一支端點**，後端依
「這個路徑目前指向什麼」跟「這個雜湊是不是已經存在別的地方」交叉判斷實際動作，呼叫端不用先自己
決定「這是新增還是更新還是改名」。

**`client_sha256` 是硬性檢查**：只要帶了 `file`，伺服器就會重新計算雜湊，跟 `client_sha256` 不一致
會回 `400`（訊息：`檔案內容與上傳前計算的雜湊不符，請重新選檔上傳。`），不是只回傳給前端自行比對——
設計上就是要擋下請求，避免預檢（precheck）後檔案內容又被改動。

### `GET /api/admin/documents`

回傳 `{ "documents": [DocumentInfo, ...] }`，一筆路徑一列（同一份內容掛兩個路徑就是兩列，各自
標籤）。每筆 `DocumentInfo` 含 `path`、`tags`（陣列）、`chunk_count`、`uploaded_at`、`file_size_bytes`、
`content_hash`、`content_changed`（列表查詢固定 `null`）。

### `POST /api/admin/documents/precheck`

批次上傳前的預檢，純讀取，不寫入、不重新 embed。請求：

```json
{
  "scope_prefix": "policy/faq/",
  "items": [
    { "path": "policy/faq/faq1.md", "client_sha256": "<sha256 hex>", "tags": ["policy"] }
  ]
}
```

- `items`：1 至 200 筆。
- `scope_prefix`：可選，只有「資料夾全量覆蓋上傳」模式才帶；用來算這次上傳沒包含到的既有路徑。

回應：

```json
{
  "items": [
    { "path": "policy/faq/faq1.md", "status": "unchanged" }
  ],
  "stale_paths": ["policy/faq/old_removed.md"]
}
```

- `status` 五選一：
  - `new`：這個路徑目前不存在，且沒有任何既有內容的雜湊跟這次的一樣。
  - `unchanged`：這個路徑本身存在、內容雜湊與 `client_sha256` 相同，且 `tags`（忽略順序）也相同——完全沒變，前端應跳過、不打任何 API。
  - `content_changed`：這個路徑本身存在，但內容雜湊與 `client_sha256` 不同，且這個新雜湊也沒有命中別的既有內容。
  - `tags_only_changed`：這個路徑本身存在、內容雜湊相同，但 `tags` 不同。
  - `linked`：這個雜湊命中**別的**既有內容（不管這個路徑本來有沒有紀錄）——判定為要掛到既有內容上，前端呼叫 `PUT` 時不需要帶 `file`，不會重新 embed。
- `stale_paths`：`scope_prefix` 底下、這次 `items` 沒包含到的既有路徑（沒帶 `scope_prefix` 固定回空陣列）——
  包含被判定 `linked` 的**來源**路徑本身（一對多模型下，`linked` 不會把舊路徑搬走，舊路徑依然是獨立有效的紀錄，
  沒被這次批次涵蓋到就照樣算待刪除候選）；前端可用這個清單詢問使用者是否要刪除「資料夾裡已經移除的舊文件」。

### `PUT /api/admin/documents/{path}`（新增/更新/改標籤/掛到既有內容，multipart form）

Form 欄位：`tags`（可重複的同名欄位，對應 `list[str]`，不帶則為空陣列）、`client_sha256`（字串，必填）、
`file`（選填）。

`file` 只有在真的需要新內容（precheck 判定 `new` 或 `content_changed`）時才要帶；`tags_only_changed`／
`linked` 不需要上傳檔案，只帶 `tags` + 目前內容的 `client_sha256` 即可。

後端內部判斷（呼叫端不用先自己分類）：

| 情境 | 動作 |
|---|---|
| 路徑沒紀錄、雜湊也沒人用過 | 需要 `file`；新增內容並真的 embed（`content_changed: true`） |
| 路徑有紀錄，雜湊／標籤都沒變 | 不動作（`content_changed: false`） |
| 路徑有紀錄，雜湊沒變，標籤變了 | 只更新標籤，不重新 embed（`content_changed: false`） |
| 路徑有紀錄，雜湊變了，且新雜湊沒人用過 | 需要 `file`；新增新內容、路徑改指向它、舊內容沒人指了就清掉（`content_changed: true`） |
| 雜湊命中別的既有內容（不管路徑本來有沒有紀錄） | 不需要 `file`；路徑改指向該既有內容，不重新 embed（`content_changed: false`）；如果路徑原本指向別的內容且該內容之後沒人指了，一併清掉 |

回應為 `DocumentInfo`：`path` 是這次的路徑，`content_hash` 就是送出的 `client_sha256`。

錯誤：非 `.md` 或非 UTF-8 回 `400`；帶了 `file` 但 `client_sha256` 與伺服器重算結果不符回 `400`；
沒帶 `file` 但路徑不存在、雜湊也沒命中任何既有內容（無法生出內容）回 `400`。

### `DELETE /api/admin/documents/{path}`

刪除這個路徑的標籤紀錄；該內容如果已經沒有其他路徑指著了，才真的刪掉向量與內容紀錄——
如果還有其他路徑在用同一份內容，只是少了這一個路徑，內容跟其他路徑不受影響。

回傳 `{ "status": "deleted", "path": "..." }`；路徑不存在回 `404`。

## 相容性要求

- 新增必填欄位、移除欄位、改名或改變 `type` 語意，均視為破壞性變更，必須同步修改前端與文件並清楚標示。
- 新增可選欄位時，舊呼叫端仍須能正常運作。
- 新增可選欄位 `has_mcp_token`（`ChatbotInfo`）與 `mcp_token`（建立／更新公司請求）時，舊呼叫端仍可正常運作。
