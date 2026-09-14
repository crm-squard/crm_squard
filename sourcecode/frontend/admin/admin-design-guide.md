# Admin 設計規範

本文件定義 Admin 新增頁面時應延續的視覺語言、版型與互動原則。實際樣式以 [src/styles.css](./src/styles.css) 與現有共用元件為準；本文件不作為執行階段依賴。

## 視覺原則

- 採用清楚、節制的淺色企業後台風格，避免過度裝飾與高彩度大面積背景。
- 以海軍藍建立文字層級，藍色表示主要操作，藍綠色作為品牌識別。
- 使用低對比邊框、柔和背景與輕量陰影區分內容，不以厚重陰影堆疊層級。
- 資訊密度以快速掃讀為主；同一頁面應維持一致的標題、卡片、表格與狀態呈現。

## 基礎樣式

### 字體

- 主要字體：`Noto Sans TC`、`PingFang TC`、`Microsoft JhengHei`，最後回退至 `sans-serif`。
- 頁面標題：`27–34px`，使用深色及略緊的字距。
- 區塊標題：`18px`。
- 內文與表格：`13–14px`；輔助資訊：`11–12px`。

### 色彩

| 用途 | 色彩 |
| --- | --- |
| 頁面背景 | `#f5f8fc` |
| 主要文字 | `#16213e` |
| 標題文字 | `#0f2148`、`#152750` |
| 次要文字 | `#71809a`、`#7b889d` |
| 主要操作 | `#1769e0` |
| 品牌藍綠 | `#11b9af`、`#1878ed` |
| 邊框 | `#e2e8f0`、`#e6ebf2` |
| 內容表面 | `rgba(255, 255, 255, .92)` |

狀態色應優先使用 Ant Design 語意色：`success`、`processing`、`warning`、`error` 與 `default`。訂單狀態的文字與色彩映射集中於 [src/components/StatusTag.tsx](./src/components/StatusTag.tsx)，新頁面不可另建重複映射。

### 圓角與間距

- 一般控制項圓角：`9–12px`。
- 卡片與內容表面圓角：`14–15px`。
- 桌面內容區：上方 `22px`、左右 `28px`、下方 `40px`。
- 區塊標題內距：上方與左右 `22–24px`，下方 `12px`。
- 同層卡片間距：`14–18px`。

Ant Design 全域 theme 設定集中於 [src/main.tsx](./src/main.tsx)，新增頁面應沿用既有 token，不在頁面內覆寫相同用途的色彩或圓角。

## 版型

後台共用殼層由 [src/components/AdminLayout.tsx](./src/components/AdminLayout.tsx) 提供，新頁面只負責內容區，不應自行建立第二組 Header 或 Sidebar。

- Sidebar 展開寬度為 `224px`，收合寬度為 `76px`。
- Header 高度為 `65px`，固定於畫面頂端。
- Sidebar 在桌面版固定於左側；行動版改用 Drawer。
- 選單區使用 `overflow-y: auto`，選項增加時由選單區獨立捲動，品牌與底部說明保持固定。
- 主要內容以 `<main>` 作為頁面根節點，依序放置頁面標題、摘要卡片與內容表面。

## 頁面元件模式

### Page Heading

- 使用 `.page-heading`，左側放置單一 `h1` 與一句頁面目的說明。
- 右側只放與整頁相關的日期、主要操作或篩選條件。
- 詳情頁使用 `.detail-heading`，返回操作放在標題前方。

### Surface 與 Section Heading

- 主要內容容器使用 `.surface`，維持一致的邊框、背景與圓角。
- 區塊標題使用 `.section-heading`，左側為 `h2` 與說明，右側為單一主要連結或控制項。
- 不在相鄰區塊使用不同的卡片陰影、圓角或背景語言。

### Metric Card

- 指標區使用 `.metric-grid` 與 `.metric-card`。
- 每張卡片只呈現一個指標、簡短標籤及一行補充資訊。
- 圖示容器使用 `.metric-icon`；顏色變體限於 `is-teal`、`is-blue`、`is-indigo`、`is-orange`。
- 尚未串接的數值應顯示明確文字，不使用看似真實的假資料。

### Table

- 訂單類表格優先重用 [src/components/OrderTable.tsx](./src/components/OrderTable.tsx)。
- 工具列使用 `.table-tools`，搜尋置左，筆數或次要操作置右。
- 表頭、字級、狀態標籤與操作連結應沿用既有樣式。
- 寬表格需提供水平捲動；行動版不得壓縮到無法辨識欄位。

### Detail

- 詳情內容使用 `.detail-surface`。
- 資訊依主題拆成多個 `h2` 區段，使用 Ant Design `Descriptions` 呈現欄位。
- 狀態標籤放在頁面標題區，避免在內容中重複顯示同一狀態。

### Loading、Empty 與 Error

- 路由載入使用 `.route-loading`，並提供 `role="status"`。
- 頁面資料載入使用 Skeleton 或 Table loading，避免顯示空白頁。
- 尚無內容或功能尚未開放時使用 Ant Design Empty，說明下一步或限制。
- API 失敗時使用 Alert 或 Result，提供可理解的訊息；可重試情境需提供重新載入操作。

## 響應式規則

| 斷點 | 行為 |
| --- | --- |
| `≤1180px` | 指標卡片由四欄改為兩欄 |
| `≤899px` | Sidebar 改為 Drawer、縮小內容內距、隱藏標題區日期 |
| `≤620px` | 指標卡片改為單欄、工具列垂直排列、縮小內容表面內距 |

新增元件時應在三個既有斷點內處理，不建立只為單一頁面服務的相近斷點。

## 可存取性與互動

- 圖示按鈕必須提供可理解的 `aria-label`，並保留 Tooltip 或可見文字。
- 所有互動控制必須可使用鍵盤操作，不以雙擊作為唯一入口。
- 狀態不可只依靠顏色辨識，必須同時顯示文字。
- 長內容與表格應提供可預期的捲動區域。
- 遵循 `prefers-reduced-motion`，不得加入無法停用的非必要動畫。
- 載入、錯誤與空狀態必須有文字說明，避免只使用圖示。

## 新增頁面檢查清單

- [ ] 使用既有 AdminLayout、Page Heading、Surface 與 Section Heading 結構。
- [ ] 優先重用現有共用元件與 Ant Design 元件，不建立相同用途的頁面專屬版本。
- [ ] 使用既有色彩、字體、圓角、間距及狀態語意。
- [ ] 已處理 loading、empty、error 與資料不足狀態。
- [ ] 已確認 `1180px`、`899px`、`620px` 三個斷點。
- [ ] 圖示按鈕、表單與導覽可使用鍵盤及輔助技術操作。
- [ ] 文件、畫面截圖與測試資料不包含個人識別資訊或本機絕對路徑。
