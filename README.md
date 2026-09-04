# CRM Squard

智慧 CRM 顧客查詢產品資訊與訂單查詢的示範專案。應用程式原始碼、啟動方式與 API 規格請見 [sourcecode/README.md](sourcecode/README.md)。

## 可選 Subagent 協作架構

本專案提供 PM、前端、後端、QA 四角色的協作架構，支援 Codex、Claude Code 與 Gemini CLI。

此架構預設關閉，不會自動建立或委派 subagent，也不影響 CRM 應用程式的執行。

若需啟用，請明確指示「啟用 subagent 架構」，再依 [AGENTS.md](AGENTS.md) 與 `.agent/instructions/project-rules.md` 的協作流程執行。

| 工具 | 預設狀態 | 啟用方式 |
| --- | --- | --- |
| Codex | 關閉 | 將 `.codex/config.toml` 的 `agents.enabled` 改為 `true`。 |
| Claude Code | 不自動委派 | 明確要求 Claude 啟用 subagent 架構。 |
| Gemini CLI | 關閉 | 將 `.gemini/settings.json` 的 `experimental.enableAgents` 改為 `true` 後重新啟動 CLI。 |
