import { useEffect, useMemo, useState } from "react";
import { deleteDocument, fetchDocuments, precheckDocuments, sha256Hex, upsertDocument } from "./api/documents";
import type { DocumentInfo, PrecheckRequestItem, PrecheckStatus } from "./types";
import "./documents.css";

const ACCEPTED_EXTENSION = ".md";
const CONCURRENCY_LIMIT = 4;

// lib.dom 的 File 型別不一定含 webkitRelativePath（非標準屬性），用交集型別擴充，
// 避免整份改用 any 而失去其餘欄位的型別檢查。
type FileWithRelativePath = File & { webkitRelativePath?: string };

type UploadMode = "files" | "folder";
type RowProgress = "pending" | "processing" | "success" | "error";

interface ProcessRow {
  path: string;
  tags: string[];
  status: PrecheckStatus;
  file: File | null;
  clientSha256: string;
  progress: RowProgress;
  errorMessage: string | null;
}

interface StaleRow {
  path: string;
  checked: boolean;
  progress: RowProgress;
  errorMessage: string | null;
}

function isMarkdownFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(ACCEPTED_EXTENSION);
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function formatUploadedAt(iso: string | null): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// 去掉前後空白與多餘斜線，非空的話補上結尾斜線，方便直接接資料夾相對路徑。
function normalizeUpperPath(upperPath: string): string {
  const trimmed = upperPath.trim().replace(/^\/+|\/+$/g, "");
  return trimmed ? `${trimmed}/` : "";
}

function getFolderModeDocIdAndTags(file: File, upperPath: string): { path: string; tags: string[] } {
  const relativePath = (file as FileWithRelativePath).webkitRelativePath || file.name;
  const folderTags = relativePath.split("/").slice(0, -1); // 資料夾各層名稱視為標籤
  const prefix = normalizeUpperPath(upperPath);
  const upperTags = prefix ? prefix.slice(0, -1).split("/").filter(Boolean) : [];
  return { path: `${prefix}${relativePath}`, tags: [...upperTags, ...folderTags] };
}

function getScopePrefix(files: File[], upperPath: string): string | null {
  if (files.length === 0) return null;
  const relativePath = (files[0] as FileWithRelativePath).webkitRelativePath;
  if (!relativePath) return null;
  const topFolder = relativePath.split("/")[0];
  return `${normalizeUpperPath(upperPath)}${topFolder}/`;
}

const PROGRESS_LABEL: Record<RowProgress, string> = {
  pending: "待處理",
  processing: "處理中...",
  success: "成功",
  error: "失敗",
};

const STATUS_LABEL: Record<PrecheckStatus, string> = {
  new: "新增",
  content_changed: "內容更新",
  tags_only_changed: "僅標籤更新",
  unchanged: "無變更",
  linked: "沿用既有內容",
};

// 有限並行處理，避免一次對後端發出過多請求。
async function runWithConcurrency<T>(items: T[], limit: number, worker: (item: T) => Promise<void>): Promise<void> {
  let cursor = 0;
  async function runNext(): Promise<void> {
    const current = cursor;
    cursor += 1;
    if (current >= items.length) return;
    await worker(items[current]);
    await runNext();
  }
  const runnerCount = Math.min(limit, items.length);
  await Promise.all(Array.from({ length: runnerCount }, () => runNext()));
}

function TagChipsInput({
  id,
  tags,
  onChange,
  placeholder,
}: {
  id: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [text, setText] = useState("");

  function commitPendingText() {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (!tags.includes(trimmed)) onChange([...tags, trimmed]);
    setText("");
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commitPendingText();
    } else if (event.key === "Backspace" && text === "" && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  }

  return (
    <div className="adp-tag-input">
      {tags.map((tag) => (
        <span key={tag} className="adp-tag-chip">
          {tag}
          <button type="button" aria-label={`移除標籤 ${tag}`} onClick={() => onChange(tags.filter((t) => t !== tag))}>
            ×
          </button>
        </span>
      ))}
      <input
        id={id}
        type="text"
        value={text}
        placeholder={placeholder}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commitPendingText}
      />
    </div>
  );
}

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [uploadMode, setUploadMode] = useState<UploadMode>("folder");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [skippedCount, setSkippedCount] = useState(0);
  const [manualTags, setManualTags] = useState<string[]>([]);
  const [upperPath, setUpperPath] = useState("");

  const [analyzing, setAnalyzing] = useState(false);
  const [precheckDone, setPrecheckDone] = useState(false);
  const [processRows, setProcessRows] = useState<ProcessRow[]>([]);
  const [staleRows, setStaleRows] = useState<StaleRow[]>([]);
  const [processing, setProcessing] = useState(false);

  const [tagFilters, setTagFilters] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");

  async function loadDocuments() {
    setLoading(true);
    setError(null);
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入文件列表失敗");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  function resetSelection() {
    setSelectedFiles([]);
    setSkippedCount(0);
    setPrecheckDone(false);
    setProcessRows([]);
    setStaleRows([]);
  }

  function handleModeChange(mode: UploadMode) {
    setUploadMode(mode);
    resetSelection();
  }

  function handleFilesInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const mdFiles = files.filter(isMarkdownFile);
    setSkippedCount(files.length - mdFiles.length);
    setSelectedFiles(mdFiles);
    setPrecheckDone(false);
    setProcessRows([]);
    setStaleRows([]);
  }

  async function analyzeSelection() {
    if (selectedFiles.length === 0) return;
    setAnalyzing(true);
    setError(null);
    setNotice(null);
    try {
      const fileEntries = selectedFiles.map((file) => {
        if (uploadMode === "files") {
          return { file, path: file.name, tags: manualTags };
        }
        const { path, tags } = getFolderModeDocIdAndTags(file, upperPath);
        return { file, path, tags };
      });

      const hashes = await Promise.all(fileEntries.map((entry) => sha256Hex(entry.file)));
      const entryByPath = new Map(fileEntries.map((entry, index) => [entry.path, { ...entry, hash: hashes[index] }]));

      const items: PrecheckRequestItem[] = fileEntries.map((entry, index) => ({
        path: entry.path,
        client_sha256: hashes[index],
        tags: entry.tags,
      }));
      const scopePrefix = uploadMode === "folder" ? getScopePrefix(selectedFiles, upperPath) : null;
      const response = await precheckDocuments(items, scopePrefix);

      const rows: ProcessRow[] = [];
      response.items.forEach((item) => {
        if (item.status === "unchanged") return;
        const entry = entryByPath.get(item.path);
        if (!entry) return;
        rows.push({
          path: item.path,
          tags: entry.tags,
          status: item.status,
          file: entry.file,
          clientSha256: entry.hash,
          progress: "pending",
          errorMessage: null,
        });
      });

      setProcessRows(rows);
      setStaleRows(
        response.stale_paths.map((path) => ({ path, checked: false, progress: "pending", errorMessage: null }))
      );
      setPrecheckDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析檔案失敗");
    } finally {
      setAnalyzing(false);
    }
  }

  function updateProcessRow(path: string, patch: Partial<ProcessRow>) {
    setProcessRows((prev) => prev.map((row) => (row.path === path ? { ...row, ...patch } : row)));
  }

  function updateStaleRow(path: string, patch: Partial<StaleRow>) {
    setStaleRows((prev) => prev.map((row) => (row.path === path ? { ...row, ...patch } : row)));
  }

  async function processOneRow(row: ProcessRow) {
    updateProcessRow(row.path, { progress: "processing", errorMessage: null });
    try {
      // new/content_changed 才需要真的帶檔案內容；tags_only_changed/linked 只改標籤紀錄，不用上傳。
      const needsFile = row.status === "new" || row.status === "content_changed";
      if (needsFile && !row.file) throw new Error("缺少檔案內容，請重新選擇檔案。");
      await upsertDocument({
        path: row.path,
        tags: row.tags,
        clientSha256: row.clientSha256,
        file: needsFile ? row.file! : undefined,
      });
      updateProcessRow(row.path, { progress: "success" });
    } catch (err) {
      updateProcessRow(row.path, {
        progress: "error",
        errorMessage: err instanceof Error ? err.message : "處理失敗",
      });
    }
  }

  async function processOneDelete(row: StaleRow) {
    updateStaleRow(row.path, { progress: "processing", errorMessage: null });
    try {
      await deleteDocument(row.path);
      updateStaleRow(row.path, { progress: "success" });
    } catch (err) {
      updateStaleRow(row.path, {
        progress: "error",
        errorMessage: err instanceof Error ? err.message : "刪除失敗",
      });
    }
  }

  async function handleStartProcessing() {
    const rowsToProcess = processRows.filter((row) => row.progress !== "success");
    const deletesToRun = staleRows.filter((row) => row.checked && row.progress !== "success");
    if (rowsToProcess.length === 0 && deletesToRun.length === 0) return;

    setProcessing(true);
    setError(null);
    setNotice(null);
    try {
      await runWithConcurrency(rowsToProcess, CONCURRENCY_LIMIT, processOneRow);
      await runWithConcurrency(deletesToRun, CONCURRENCY_LIMIT, processOneDelete);
      setNotice("批次處理完成，已重新整理文件列表。");
      await loadDocuments();
    } finally {
      setProcessing(false);
    }
  }

  const allTags = useMemo(() => Array.from(new Set(documents.flatMap((doc) => doc.tags))).sort(), [documents]);

  const filteredDocuments = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    return documents.filter((doc) => {
      const matchesKeyword = keyword === "" || doc.path.toLowerCase().includes(keyword);
      const matchesTags = tagFilters.length === 0 || tagFilters.some((tag) => doc.tags.includes(tag));
      return matchesKeyword && matchesTags;
    });
  }, [documents, searchText, tagFilters]);

  function toggleTagFilter(tag: string) {
    setTagFilters((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
  }

  async function handleDelete(path: string) {
    const confirmed = window.confirm(`確定要刪除文件「${path}」嗎？此操作無法復原。`);
    if (!confirmed) return;
    setError(null);
    setNotice(null);
    try {
      await deleteDocument(path);
      setDocuments((prev) => prev.filter((doc) => doc.path !== path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "刪除文件失敗");
    }
  }

  return (
    <div className="adp-root">
      <div className="adp-container">
        <h1 className="adp-title">知識庫文件管理</h1>
        <p className="adp-subtitle">上傳、更新或刪除供聊天機器人 RAG 檢索使用的知識庫文件（目前只支援 .md 檔案）。</p>

        {error && <div className="adp-error">{error}</div>}
        {notice && <div className="adp-notice">{notice}</div>}

        <section className="adp-card">
          <h2 className="adp-card-title">新增 / 更新文件</h2>

          <div className="adp-mode-toggle">
            <label>
              <input
                type="radio"
                name="adp-upload-mode"
                checked={uploadMode === "files"}
                onChange={() => handleModeChange("files")}
              />
              選擇多個檔案
            </label>
            <label>
              <input
                type="radio"
                name="adp-upload-mode"
                checked={uploadMode === "folder"}
                onChange={() => handleModeChange("folder")}
              />
              選擇資料夾（局部覆蓋）
            </label>
          </div>

          {uploadMode === "files" && (
            <div className="adp-form-row">
              <div className="adp-field">
                <label htmlFor="adp-files-input">選擇檔案（僅限 .md，路徑沿用檔名）</label>
                <input id="adp-files-input" type="file" accept={ACCEPTED_EXTENSION} multiple onChange={handleFilesInputChange} />
              </div>
              <div className="adp-field">
                <label htmlFor="adp-manual-tags">標籤（Enter 或逗號分隔，套用到這批全部檔案）</label>
                <TagChipsInput id="adp-manual-tags" tags={manualTags} onChange={setManualTags} placeholder="輸入標籤後按 Enter" />
              </div>
            </div>
          )}

          {uploadMode === "folder" && (
            <div className="adp-form-row">
              <div className="adp-field">
                <label htmlFor="adp-folder-input">選擇資料夾（可選任一層子資料夾，僅處理其中的 .md 檔）</label>
                <input
                  id="adp-folder-input"
                  type="file"
                  multiple
                  onChange={handleFilesInputChange}
                  {...({ webkitdirectory: "true" } as Record<string, string>)}
                />
              </div>
              <div className="adp-field">
                <label htmlFor="adp-upper-path">上層路徑（貼選取資料夾與根目錄的差距，選填）</label>
                <input
                  id="adp-upper-path"
                  type="text"
                  value={upperPath}
                  onChange={(event) => setUpperPath(event.target.value)}
                  placeholder="例如 policy/knowledge"
                />
              </div>
            </div>
          )}

          {skippedCount > 0 && <p className="adp-notice-inline">已略過 {skippedCount} 個非 .md 檔案。</p>}
          {selectedFiles.length > 0 && (
            <p className="adp-notice-inline">已選取 {selectedFiles.length} 個 .md 檔案。</p>
          )}

          <button
            type="button"
            className="adp-btn"
            disabled={selectedFiles.length === 0 || analyzing}
            onClick={analyzeSelection}
          >
            {analyzing ? "分析中..." : "分析檔案"}
          </button>

          {precheckDone && (
            <div className="adp-review">
              {staleRows.length > 0 && (
                <div className="adp-review-group">
                  <h3>待刪除的舊文件（此範圍下這次未包含到的路徑，請自行確認勾選）</h3>
                  <ul className="adp-stale-list">
                    {staleRows.map((row) => (
                      <li key={row.path}>
                        <label>
                          <input
                            type="checkbox"
                            checked={row.checked}
                            onChange={(event) => updateStaleRow(row.path, { checked: event.target.checked })}
                          />
                          {row.path}
                        </label>
                        <span className={`adp-status adp-status-${row.progress}`}>{PROGRESS_LABEL[row.progress]}</span>
                        {row.progress === "error" && (
                          <>
                            <span className="adp-row-error">{row.errorMessage}</span>
                            <button type="button" className="adp-btn-secondary adp-btn" onClick={() => processOneDelete(row)}>
                              重試
                            </button>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="adp-review-group">
                <h3>這次要處理的文件</h3>
                {processRows.length === 0 && <p className="adp-empty">無需處理的項目。</p>}
                {processRows.length > 0 && (
                  <table className="adp-table">
                    <thead>
                      <tr>
                        <th>路徑</th>
                        <th>標籤</th>
                        <th>動作</th>
                        <th>狀態</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {processRows.map((row) => (
                        <tr key={row.path}>
                          <td>{row.path}</td>
                          <td>
                            <div className="adp-tag-chips-static">
                              {row.tags.map((tag) => (
                                <span key={tag} className="adp-tag-chip-static">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td>{STATUS_LABEL[row.status]}</td>
                          <td>
                            <span className={`adp-status adp-status-${row.progress}`}>{PROGRESS_LABEL[row.progress]}</span>
                            {row.progress === "error" && <div className="adp-row-error">{row.errorMessage}</div>}
                          </td>
                          <td>
                            {row.progress === "error" && (
                              <button type="button" className="adp-btn-secondary adp-btn" onClick={() => processOneRow(row)}>
                                重試
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="adp-row-actions">
                <button
                  type="button"
                  className="adp-btn"
                  disabled={processing}
                  onClick={handleStartProcessing}
                >
                  {processing ? "處理中..." : "開始處理"}
                </button>
                <button type="button" className="adp-btn-secondary adp-btn" disabled={processing} onClick={resetSelection}>
                  重新選擇
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="adp-card">
          <h2 className="adp-card-title">文件列表</h2>

          <div className="adp-form-row">
            <div className="adp-field">
              <label htmlFor="adp-search">路徑關鍵字搜尋</label>
              <input
                id="adp-search"
                type="text"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="輸入路徑關鍵字"
              />
            </div>
            <div className="adp-field">
              <label>標籤篩選</label>
              <div className="adp-tag-filter-list">
                {allTags.length === 0 && <span className="adp-empty">尚無標籤</span>}
                {allTags.map((tag) => (
                  <label key={tag} className="adp-tag-filter-item">
                    <input type="checkbox" checked={tagFilters.includes(tag)} onChange={() => toggleTagFilter(tag)} />
                    {tag}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {loading && <p className="adp-loading">載入中...</p>}
          {!loading && filteredDocuments.length === 0 && <p className="adp-empty">目前沒有符合條件的文件。</p>}
          {!loading && filteredDocuments.length > 0 && (
            <table className="adp-table">
              <thead>
                <tr>
                  <th>路徑</th>
                  <th>標籤</th>
                  <th>Chunk 數量</th>
                  <th>檔案大小</th>
                  <th>更新時間</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocuments.map((doc) => (
                  <tr key={doc.path}>
                    <td>{doc.path}</td>
                    <td>
                      <div className="adp-tag-chips-static">
                        {doc.tags.map((tag) => (
                          <span key={tag} className="adp-tag-chip-static">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{doc.chunk_count}</td>
                    <td>{formatBytes(doc.file_size_bytes)}</td>
                    <td>{formatUploadedAt(doc.uploaded_at)}</td>
                    <td>
                      <div className="adp-row-actions">
                        <button type="button" className="adp-btn-danger adp-btn" onClick={() => handleDelete(doc.path)}>
                          刪除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
