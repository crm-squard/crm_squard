# Codex 專案指令

處理此專案前，先讀取並遵循下列共用文件：

1. `.agent/instructions/project-rules.md`
2. 任務涉及 CRM 前後端、RAG、LLM provider、訂單或產品文案時，讀取 `.agent/skills/crm-development/SKILL.md`

共用文件是跨 Agent 的唯一規格來源。若本檔與共用文件牴觸，以共用文件為準；Codex 平台本身的安全與權限限制除外。

## 可選 Subagent 協作架構

本專案提供 PM、前端、後端、QA 四角色的 subagent 協作架構，目前預設未啟用。

開始工作時，先提示：「偵測到可選 subagent 協作架構，目前未啟用；如需 PM、前端、後端、QA 分工，請明確要求啟用。」

未收到使用者明確要求「啟用 subagent 架構」或指定啟用某個角色前，不得建立、委派或自動使用 subagent。啟用後仍須遵守 `.agent/instructions/project-rules.md` 的角色責任域與交接流程。
