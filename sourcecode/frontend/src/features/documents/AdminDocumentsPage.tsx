import { useEffect, useState } from "react";
import { createDocument, deleteDocument, fetchDocuments, updateDocument } from "./api/documents";
import type { DocumentCategory, DocumentInfo } from "./types";
import "./documents.css";

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [newSource, setNewSource] = useState("");
  const [newCategory, setNewCategory] = useState<DocumentCategory>("product");
  const [newContent, setNewContent] = useState("");

  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
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

  async function handleCreateSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!newSource.trim() || !newContent.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createDocument({ source: newSource.trim(), category: newCategory, content: newContent });
      setNewSource("");
      setNewContent("");
      setNewCategory("product");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "新增文件失敗");
    } finally {
      setSubmitting(false);
    }
  }

  function startEditing(docId: string) {
    setEditingDocId(docId);
    setEditingContent("");
    setError(null);
  }

  function cancelEditing() {
    setEditingDocId(null);
    setEditingContent("");
  }

  async function handleUpdateSubmit(docId: string) {
    if (!editingContent.trim()) return;
    setEditingSubmitting(true);
    setError(null);
    try {
      await updateDocument(docId, { content: editingContent });
      cancelEditing();
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
        <p className="adp-subtitle">新增、編輯或刪除供聊天機器人 RAG 檢索使用的知識庫文件。</p>

        {error && <div className="adp-error">{error}</div>}

        <section className="adp-card">
          <h2 className="adp-card-title">新增文件</h2>
          <form onSubmit={handleCreateSubmit}>
            <div className="adp-form-row">
              <div className="adp-field">
                <label htmlFor="adp-new-source">來源名稱（doc_id）</label>
                <input
                  id="adp-new-source"
                  type="text"
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  placeholder="例如：product_wireless_mouse"
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
            <div className="adp-field" style={{ marginBottom: 12 }}>
              <label htmlFor="adp-new-content">內容（Markdown 原文）</label>
              <textarea
                id="adp-new-content"
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="貼上完整的 Markdown 原文"
                required
              />
            </div>
            <button type="submit" className="adp-btn" disabled={submitting}>
              {submitting ? "新增中..." : "新增文件"}
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
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.doc_id}>
                    <td>{doc.doc_id}</td>
                    <td>{doc.category}</td>
                    <td>{doc.chunk_count}</td>
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
                            輸入新內容以整份覆蓋（目前系統不會預先帶入舊內容）
                          </label>
                          <textarea
                            id={`adp-edit-${doc.doc_id}`}
                            value={editingContent}
                            onChange={(e) => setEditingContent(e.target.value)}
                            placeholder="貼上完整的新版 Markdown 原文"
                          />
                          <div className="adp-row-actions">
                            <button
                              type="button"
                              className="adp-btn"
                              onClick={() => handleUpdateSubmit(doc.doc_id)}
                              disabled={editingSubmitting}
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
