"""
「LlamaIndex」RAG 引擎：用 LlamaIndex 的 VectorStoreIndex + pgvector（PostgreSQL）取代原本
的本地磁碟 persist，換取 LlamaIndex 原生的 insert_nodes/delete_ref_doc 增量更新能力，讓
app/rag/documents_store.py 能做單一文件的新增/刪除/更新，不用整批重建索引。
跟 online_engine.py 提供同一種介面 retrieve(query, top_k)，方便用 RAG_ENGINE 設定切換。

語意拆分（產品的介紹/規格/彩蛋、政策文件的各小節）沿用 app/rag/product_parser.py /
app/rag/policy_parser.py 的純函式規則，「怎麼切」是文件格式特有的知識，跟「用哪套框架做
向量索引/檢索」是兩件事；app/rag/documents_store.py 負責把 parser 輸出的 chunk 包成
LlamaIndex 的 TextNode 並寫進 pgvector。

索引資料存在 settings.RAG_PG_* 指定的 PostgreSQL（pgvector extension），服務啟動時若該
table 是空的，會由 documents_store.seed_if_empty() 自動把 app/data/ 下既有的知識庫文件灌入
（一次性、冪等）；之後要新增/刪除/更新單一文件改走 /api/admin/documents 系列 API，不用再
手動清資料重建索引。
"""
from llama_index.core import Settings as LlamaSettings
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

from app.config import settings

# intfloat/multilingual-e5-base 輸出 768 維，PGVectorStore 建表時的向量欄位維度要對齊這個數字
EMBED_DIM = 768


def _get_embed_model():
    # e5 系列模型需要 "query: " / "passage: " 前綴才能發揮非對稱檢索的效果，
    # HuggingFaceEmbedding 的 query_instruction/text_instruction 剛好對應這兩個前綴。
    return HuggingFaceEmbedding(
        model_name=settings.EMBEDDING_MODEL_NAME,
        query_instruction="query: ",
        text_instruction="passage: ",
    )


def _get_vector_store() -> PGVectorStore:
    return PGVectorStore.from_params(
        host=settings.RAG_PG_HOST,
        port=str(settings.RAG_PG_PORT),
        database=settings.RAG_PG_DATABASE,
        user=settings.RAG_PG_USER,
        password=settings.RAG_PG_PASSWORD,
        table_name=settings.RAG_PG_TABLE,
        embed_dim=EMBED_DIM,
    )


class LlamaIndexRetriever:
    name = "llamaindex"

    def __init__(self):
        LlamaSettings.embed_model = _get_embed_model()
        LlamaSettings.llm = None  # 這裡只用 LlamaIndex 做檢索，生成交給 app/providers.py 統一處理

        self.vector_store = _get_vector_store()
        # from_vector_store() 直接掛載既有向量資料，不會重新 embed（跟舊版
        # load_index_from_storage() 對本地磁碟 persist 的效果相同，只是後端換成 pgvector）
        self.index = VectorStoreIndex.from_vector_store(
            self.vector_store, embed_model=LlamaSettings.embed_model
        )

        # 延遲 import 避免循環 import（documents_store.py 也會用到本模組建立的 index 型別）
        from app.rag.documents_store import seed_if_empty
        seed_if_empty(self.index)

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        retrieved = []
        for n in nodes:
            meta = n.node.metadata
            # LlamaIndex 的 score 是「相似度」（越高越相關），統一轉成 distance（越低越相關），
            # 讓 agent.py 的 NO_INFO_DISTANCE_THRESHOLD 判斷邏輯跟 online_engine.py 共用；
            # 但兩套引擎的分數尺度本來就不同，門檻值不能直接共用同一個數字
            # （見 app/config.py 的 RAG_NO_INFO_THRESHOLDS）。
            score = n.score if n.score is not None else 0.0
            retrieved.append({
                "text": n.node.get_content(),
                "source": meta.get("source", ""),
                "topic": meta.get("topic", ""),
                "category": meta.get("category", ""),
                "distance": 1 - score,
            })
        return retrieved
