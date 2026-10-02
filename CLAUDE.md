# Claude 專案指令

處理此專案前，先讀取並遵循下列共用文件：

1. `.agent/instructions/project-rules.md`
2. 任務涉及 CRM 前後端、RAG、LLM provider、訂單或產品文案時，讀取 `.agent/skills/crm-development/SKILL.md`
3. 任務涉及 React 前端開發、審查、重構或效能優化時，載入全域 `vercel-react-best-practices` Skill；目前專案使用 React 18，只套用 React 18 相容規則，排除 React 19、React Compiler、Server Components 與 Next.js 專屬規則。
4. 任務涉及前端樣式時，必須遵循 `.agent/instructions/project-rules.md` 的「前端 Tailwind CSS v4 架構」。

共用文件是跨 Agent 的唯一規格來源。若本檔與共用文件牴觸，以共用文件為準；Claude 平台本身的安全與權限限制除外。

# Subagent 套件安裝說明

這個壓縮檔裡包含 4 個 Claude Code subagent，已加上 `memory: project` 讓每個角色能跨 session 累積自己的知識。

## 資料夾結構

```
.claude/
└── agents/
    ├── frontend-developer.md
    ├── backend-developer.md
    ├── qa-test-engineer.md
    └── security-auditor.md
```

## 安裝方式

1. 解壓縮這個檔案。
2. 把裡面的 `.claude` 資料夾整個複製到你的專案根目錄（跟 `.git` 同一層）。
   - 如果專案裡已經有 `.claude` 資料夾，只需要把 `agents` 子資料夾合併進去即可，不要整個覆蓋。
3. 若這是你在這個專案第一次新增 `.claude/agents/`（原本完全沒有這個資料夾），需要**重新啟動 Claude Code**才會偵測到；之後修改檔案內容則會自動偵測，不用重啟。
4. 建議把 `.claude/agents/` 加入 git 版本控制，讓組員共用同一套角色設定；`.claude/agent-memory/`（各角色自己的記憶檔，第一次執行後才會產生）也建議加入版本控制，讓所有人共享累積下來的知識。

## 使用方式

自動委派（不用特別指定，Claude 會依任務內容自動判斷）：

```
幫我做訂單查詢的 API
```

明確指定：

```
用 security-auditor 檢查一下這次的認證邏輯改動
```

串接多個角色：

```
用 backend-developer 實作訂單查詢 API，完成後用 qa-test-engineer 補測試，
測試通過後用 security-auditor 檢查一次
```

## 記憶功能

每個角色會在 `.claude/agent-memory/<角色名稱>/` 底下累積自己的知識，跨 session 保留。第一次使用某個角色前記憶是空的，屬正常現象——用得越多，累積的知識越多。

可以主動請它們讀取或更新記憶，例如：

```
用 security-auditor 檢查這次改動，先看看你之前記錄過的模式
```
```
稽核完成了，把你這次學到的存到記憶裡
```
