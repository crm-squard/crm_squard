export type DocumentCategory = "product" | "policy";

export interface DocumentInfo {
  doc_id: string;
  category: DocumentCategory;
  chunk_count: number;
  content_changed: boolean | null;
  uploaded_at: string | null;
  file_size_bytes: number | null;
  duplicate_of: string | null;
}
