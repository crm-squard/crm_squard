# CRM Squad 共用專案規則

## 專案邊界

- 可執行專案位於 `sourcecode/`；後端位於 `sourcecode/backend/`，前端位於 `sourcecode/frontend/`。
- 修改前先讀取相關入口、型別、設定與呼叫端，維持既有資料流與專案慣例。
- 採最小可行修改，處理根因；不要順帶重構、重新命名或調整無關檔案。
- 保留團隊現有變更。發現不相關的未提交內容時，不覆蓋、不還原。

## 程式與文件

- 變數與函式名稱使用英文；註解使用繁體中文，說明設計原因或限制。
- Python 沿用現有 FastAPI、Pydantic 與模組分工；React 沿用現有函式元件與 hooks 寫法。
- API 欄位或回應型別變更時，同步檢查 Pydantic schema、route、前端呼叫端與文件。
- 不在程式碼、文件、測試輸出或提交內容中放入 API key、token、`.env` 或真實顧客資料。

## 驗證與交付

- 依變更範圍執行必要的後端檢查或前端 `npm run build`；不要以未執行的測試宣稱通過。
- 完成後回報修改檔案、關鍵行號、驗證結果與已知限制。
- Commit message 使用 Conventional Commits，描述使用繁體中文，例如 `docs: 新增跨 Agent 共用規格`。

## 可選 Subagent 協作架構

- 本專案提供 PM、前端、後端、QA 四角色的 subagent 協作架構，預設未啟用。
- 未收到使用者明確要求「啟用 subagent 架構」或指定啟用角色前，不得建立、委派或自動使用 subagent。
- 啟用後由 PM 釐清需求、鎖定 API 契約與驗收條件；前端與後端依契約平行實作；QA 唯讀驗證並回報可重現問題；PM 彙整交付。
- PM 不直接實作前端或後端功能；前端僅修改 `sourcecode/frontend/`；後端僅修改 `sourcecode/backend/`；QA 不得修改產品程式碼或設定。
- 每個角色完成工作時，須回報變更或檢查檔案、API 契約影響、執行命令與結果、未驗證風險及下一個交接角色。
