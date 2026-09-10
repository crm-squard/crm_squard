import type { DocumentCategory, DocumentInfo } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents`);
  await throwIfNotOk(response);
  const data = (await response.json()) as { documents: DocumentInfo[] };
  return data.documents;
}

export async function createDocument(file: File, category: DocumentCategory): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  const response = await fetch(`${API_BASE_URL}/api/admin/documents`, {
    method: "POST",
    body: formData,
  });
  await throwIfNotOk(response);
  return (await response.json()) as DocumentInfo;
}

export async function updateDocument(docId: string, file: File): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/admin/documents/${encodeURIComponent(docId)}`, {
    method: "PUT",
    body: formData,
  });
  await throwIfNotOk(response);
  return (await response.json()) as DocumentInfo;
}

export async function deleteDocument(docId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  await throwIfNotOk(response);
}
