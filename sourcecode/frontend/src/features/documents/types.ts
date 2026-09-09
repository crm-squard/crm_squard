export type DocumentCategory = "product" | "policy";

export interface DocumentInfo {
  doc_id: string;
  category: DocumentCategory;
  chunk_count: number;
}

export interface DocumentCreateInput {
  source: string;
  category: DocumentCategory;
  content: string;
}

export interface DocumentUpdateInput {
  content: string;
}
