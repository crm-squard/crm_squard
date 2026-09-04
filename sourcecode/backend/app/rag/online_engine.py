"""
線上 RAG 檢索引擎 (Google Gemini Embeddings + Chroma DB)。

提供統一檢索介面：
    retrieve(query: str, top_k: int) -> [{"text", "source", "topic", "category", "distance"}]
"""
import os
import chromadb
from app.config import settings
from app.documents import get_all_chunks
from app.rag.embedding_online import embed_passages_online, embed_query_online


class OnlineRetriever:
    name = "online"

    def __init__(self):
        persist_dir = getattr(settings, "CHROMA_ONLINE_PERSIST_DIR", "./chroma_online_data")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="crm_online_rag", metadata={"hnsw:space": "l2"}
        )

        if self.collection.count() == 0:
            self._build_index()

    def _build_index(self):
        chunks = get_all_chunks()
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        embeddings = embed_passages_online(texts)

        ids = [f"doc_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "source": c["source"],
                "topic": c["topic"],
                "category": c["category"],
                "product_id": c["product_id"] or "",
            }
            for c in chunks
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = embed_query_online(query)
        results = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        retrieved = []
        if results and results.get("documents") and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ):
                retrieved.append({
                    "text": doc,
                    "source": meta["source"],
                    "topic": meta.get("topic", ""),
                    "category": meta.get("category", ""),
                    "distance": dist,
                })
        return retrieved
