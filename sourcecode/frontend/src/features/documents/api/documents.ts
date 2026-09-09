import type { DocumentCreateInput, DocumentInfo, DocumentUpdateInput } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents`);
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
  const data = (await response.json()) as { documents: DocumentInfo[] };
  return data.documents;
}

export async function createDocument(input: DocumentCreateInput): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function updateDocument(docId: string, input: DocumentUpdateInput): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents/${encodeURIComponent(docId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function deleteDocument(docId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}
