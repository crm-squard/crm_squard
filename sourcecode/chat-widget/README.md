# CRM Chat Widget

獨立 React 18 聊天元件，建置後只需部署 `dist/chat-widget.js`。

## 建置

```bash
npm install
cp .env.example .env
npm run preview
```

`npm run preview` 會依序完成建置、注入目標專案，再於 `http://localhost:5175` 啟動預覽服務。開啟此網址即可直接查看 Chat Widget 介面；`http://localhost:5175/chat-widget.js` 則保留給其他網站嵌入。

## 開發環境注入

`.env` 的 `CHAT_WIDGET_INJECT_TARGET_DIR` 用來指定開發階段的目標前端專案，預設為同層的 `../corp-frontend`：

```env
CHAT_WIDGET_INJECT_TARGET_DIR=../corp-frontend
```

`npm run preview` 會自動將建置結果複製至目標專案的 `public/src/chat-widget.js`，並確認 `index.html` 已有注入標籤。Corp Frontend 開發環境會透過 `/src/chat-widget.js` 載入此檔案。

若只需複製與注入而不啟動預覽，可執行：

```bash
npm run inject:target
```

此設定只供本機開發工具讀取，不會打包至 `chat-widget.js`。正式提供客戶使用時，不需要設定目標目錄，直接提供下方嵌入程式碼即可。

## 嵌入

```html
<script
  src="https://<widget-service>/chat-widget.js"
  data-client-id="<assigned-client-id>"
  defer
></script>
```

`data-client-id` 是公開的企業客戶識別碼，不是登入或授權憑證。此值現在對應後端 `companies` 表的
company_id（透過 `/api/admin/companies` 建立/查詢），沒有對應公司時聊天功能仍可用，但訂單查詢／RAG
檢索會查不到任何資料。正式資料隔離仍須由後端驗證客戶狀態並限制資料範圍。
