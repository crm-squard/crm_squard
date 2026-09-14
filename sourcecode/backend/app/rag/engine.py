"""
RAG 檢索引擎入口：目前只有 llamaindex 一套實作（LlamaIndex VectorStoreIndex + pgvector，
本地 embedding），介面：
    retrieve(query: str, top_k: int) -> [{"text","source","topic","category","distance"}]
agent.py 只依賴這個介面，不需要知道背後實作細節。

（原本還有兩套：自製的 "custom" 引擎（Chroma + 手寫檢索）已隨 llamaindex 引擎改用 pgvector
一起退休；線上 "online"/"gemini"（Google Gemini embedding + Chroma）引擎也已移除，RAG
embedding 統一改用 llamaindex 本地 embedding，不再依賴線上 embedding API。）
"""
from app.rag.llamaindex_engine import LlamaIndexRetriever

_retriever = None


def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = LlamaIndexRetriever()
    return _retriever
