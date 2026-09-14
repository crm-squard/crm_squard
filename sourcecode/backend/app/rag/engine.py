"""
RAG 引擎切換：依 settings.RAG_ENGINE（"llamaindex" | "online" | "gemini"）決定用哪一套檢索實作。

各引擎都提供同一種介面：
    retrieve(query: str, top_k: int) -> [{"text","source","topic","category","distance"}]
agent.py 只依賴這個介面，不需要知道背後是哪一套，因此可以直接切換 .env 的 RAG_ENGINE 改用另一套，
不用改任何呼叫端程式碼。

（原本還有一套自製的 "custom" 引擎（Chroma + 手寫檢索），已隨 llamaindex 引擎改用 pgvector
一起退休，理由是 llamaindex 引擎現在已能提供原生的增量更新能力，不再需要維護兩套本地引擎。）
"""
from app.config import settings

_retriever = None


def get_retriever():
    global _retriever
    if _retriever is not None:
        return _retriever

    if settings.RAG_ENGINE == "llamaindex":
        from app.rag.llamaindex_engine import LlamaIndexRetriever
        _retriever = LlamaIndexRetriever()
    elif settings.RAG_ENGINE in ("online", "gemini"):
        from app.rag.online_engine import OnlineRetriever
        _retriever = OnlineRetriever()
    else:
        raise ValueError(f"未知的 RAG_ENGINE 設定：{settings.RAG_ENGINE}（可用值：llamaindex, online）")

    return _retriever
