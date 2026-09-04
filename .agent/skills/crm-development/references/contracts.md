# CRM 介面契約

修改 API 或前後端資料流時讀取本文件。實際型別來源為 `sourcecode/backend/app/schemas.py`，FastAPI 產生的 OpenAPI schema 可作為機器可讀契約。

## `POST /api/chat`

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
- `order`：包含 `code`、`status`、`eta` 與 `items`。
- `text`：包含 `text`，用於提示、查無資料或可理解的錯誤訊息。

## 其他端點

- `GET /health`：回傳 `{ "status": "ok" }`。
- `POST /api/warmup`：載入模型後回傳狀態。
- `GET /api/providers`：回傳 provider 的 `id`、`label` 與 `configured`。
- `GET /api/admin/summary?date=YYYY-MM-DD`：回傳 `date`、`question_count` 與 `summary`；此端點目前沒有身分驗證。

## 相容性要求

- 新增必填欄位、移除欄位、改名或改變 `type` 語意，均視為破壞性變更，必須同步修改前端與文件並清楚標示。
- 新增可選欄位時，舊呼叫端仍須能正常運作。
- 訂單編號目前採 1 個英文字母加 5 位數字，例如 `A12345`。
