import { useEffect, useRef, useState } from "react";
import { createDocument, deleteDocument, fetchDocuments, updateDocument } from "./api/documents";
import type { DocumentCategory, DocumentInfo } from "./types";
import "./documents.css";

const ACCEPTED_EXTENSION = ".md";

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

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [newFile, setNewFile] = useState<File | null>(null);
  const [newCategory, setNewCategory] = useState<DocumentCategory>("product");
  const newFileInputRef = useRef<HTMLInputElement>(null);

  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editingFile, setEditingFile] = useState<File | null>(null);
  const [editingSubmitting, setEditingSubmitting] = useState(false);

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

  function handleNewFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (file && !isMarkdownFile(file)) {
      setError(`「${file.name}」不是 .md 檔，目前只支援 .md 檔案。`);
      event.target.value = "";
      setNewFile(null);
      return;
    }
    setError(null);
    setNewFile(file);
  }

  async function handleCreateSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!newFile) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createDocument(newFile, newCategory);
      setNewFile(null);
      setNewCategory("product");
      if (newFileInputRef.current) newFileInputRef.current.value = "";
      if (result.duplicate_of) {
        setNotice(`新增成功，但內容跟現有文件「${result.duplicate_of}」完全一樣，請確認是否重複上傳。`);
      } else {
        setNotice(`已新增「${result.doc_id}」。`);
      }
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "新增文件失敗");
    } finally {
      setSubmitting(false);
    }
  }

  function startEditing(docId: string) {
    setEditingDocId(docId);
    setEditingFile(null);
    setError(null);
    setNotice(null);
  }

  function cancelEditing() {
    setEditingDocId(null);
    setEditingFile(null);
  }

  function handleEditingFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (file && !isMarkdownFile(file)) {
      setError(`「${file.name}」不是 .md 檔，目前只支援 .md 檔案。`);
      event.target.value = "";
      setEditingFile(null);
      return;
    }
    setError(null);
    setEditingFile(file);
  }

  async function handleUpdateSubmit(docId: string) {
    if (!editingFile) return;
    setEditingSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const result = await updateDocument(docId, editingFile);
      cancelEditing();
      if (!result.content_changed) {
        setNotice(`「${docId}」內容跟原本一樣，未重新產生向量。`);
      } else if (result.duplicate_of) {
        setNotice(`更新成功，但內容跟現有文件「${result.duplicate_of}」完全一樣，請確認是否重複。`);
      } else {
        setNotice(`已更新「${docId}」。`);
      }
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新文件失敗");
    } finally {
      setEditingSubmitting(false);
    }
  }

  async function handleDelete(docId: string) {
    const confirmed = window.confirm(`確定要刪除文件「${docId}」嗎？此操作無法復原。`);
    if (!confirmed) return;
    setError(null);
    setNotice(null);
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((doc) => doc.doc_id !== docId));
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
          <h2 className="adp-card-title">新增文件</h2>
          <form onSubmit={handleCreateSubmit}>
            <div className="adp-form-row">
              <div className="adp-field">
                <label htmlFor="adp-new-file">選擇檔案（僅限 .md，doc_id 沿用檔名）</label>
                <input
                  id="adp-new-file"
                  ref={newFileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSION}
                  onChange={handleNewFileChange}
                  required
                />
              </div>
              <div className="adp-field">
                <label htmlFor="adp-new-category">分類</label>
                <select
                  id="adp-new-category"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as DocumentCategory)}
                >
                  <option value="product">product</option>
                  <option value="policy">policy</option>
                </select>
              </div>
            </div>
            <button type="submit" className="adp-btn" disabled={submitting || !newFile}>
              {submitting ? "上傳中..." : "上傳文件"}
            </button>
          </form>
        </section>

        <section className="adp-card">
          <h2 className="adp-card-title">文件列表</h2>
          {loading && <p className="adp-loading">載入中...</p>}
          {!loading && documents.length === 0 && <p className="adp-empty">目前沒有任何文件。</p>}
          {!loading && documents.length > 0 && (
            <table className="adp-table">
              <thead>
                <tr>
                  <th>doc_id</th>
                  <th>分類</th>
                  <th>Chunk 數量</th>
                  <th>檔案大小</th>
                  <th>上傳時間</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.doc_id}>
                    <td>{doc.doc_id}</td>
                    <td>{doc.category}</td>
                    <td>{doc.chunk_count}</td>
                    <td>{formatBytes(doc.file_size_bytes)}</td>
                    <td>{formatUploadedAt(doc.uploaded_at)}</td>
                    <td>
                      <div className="adp-row-actions">
                        <button
                          type="button"
                          className="adp-btn-secondary adp-btn"
                          onClick={() => startEditing(doc.doc_id)}
                        >
                          編輯
                        </button>
                        <button
                          type="button"
                          className="adp-btn-danger adp-btn"
                          onClick={() => handleDelete(doc.doc_id)}
                        >
                          刪除
                        </button>
                      </div>
                      {editingDocId === doc.doc_id && (
                        <div className="adp-edit-panel">
                          <label htmlFor={`adp-edit-${doc.doc_id}`}>
                            上傳新版 .md 檔以整份覆蓋內容（檔名不用跟 doc_id 一樣）
                          </label>
                          <input
                            id={`adp-edit-${doc.doc_id}`}
                            type="file"
                            accept={ACCEPTED_EXTENSION}
                            onChange={handleEditingFileChange}
                          />
                          <div className="adp-row-actions">
                            <button
                              type="button"
                              className="adp-btn"
                              onClick={() => handleUpdateSubmit(doc.doc_id)}
                              disabled={editingSubmitting || !editingFile}
                            >
                              {editingSubmitting ? "更新中..." : "儲存更新"}
                            </button>
                            <button type="button" className="adp-btn-secondary adp-btn" onClick={cancelEditing}>
                              取消
                            </button>
                          </div>
                        </div>
                      )}
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
