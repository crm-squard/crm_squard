"""
文檔管理核心邏輯：新增/刪除/更新/列出 pgvector（llamaindex 引擎）裡的知識庫文件。

不另外保存文件原文：pgvector 的 node 表（chunk 文字 + 向量 + metadata）就是唯一資料來源，
「更新」= 刪除該文件舊 chunk + 插入新 chunk，不做差異比對。

實作上有兩個容易出錯、已用實際安裝的 llama-index-core==0.11.17 /
llama-index-vector-stores-postgres==0.2.6 原始碼確認過的細節（不是照文件/計畫骨架直接假設）：

1. `TextNode(..., ref_doc_id=source)` 這種建構子寫法會被靜默忽略（TextNode 沒有 ref_doc_id
   欄位，pydantic 不會報錯但值還是 None）。ref_doc_id 要透過
   `node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=source)` 設定，
   pgvector 的 delete()／VectorStoreIndex.delete_ref_doc() 才能用這個值篩選、刪掉同一份
   文件的所有 chunk（llama_index/vector_stores/postgres/base.py 的 delete() 是用
   `metadata_["doc_id"].astext == ref_doc_id` 做 SQL 篩選，這個 doc_id 就是從
   node.ref_doc_id 存進去的）。
2. `PGVectorStore.from_params(table_name="kb_chunks", ...)` 實際建立的實體資料表名稱是
   `data_kb_chunks`（見 get_data_model() 的 `tablename = "data_%s" % index_name`），
   不是 "kb_chunks" 本身；list_documents() 這裡要直接對實體表下 SQL，必須對齊這個命名規則。
"""
from typing import Literal, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from sqlalchemy import create_engine
from sqlalchemy import text as sql_text

from app.config import settings
from app.documents import get_seed_sources
from app.rag.policy_parser import parse_policy_doc
from app.rag.product_parser import parse_products

Category = Literal["product", "policy"]


def _parse(category: Category, raw_text: str, source: str) -> list[dict]:
    if category == "product":
        return parse_products(raw_text, source=source)
    if category == "policy":
        return parse_policy_doc(raw_text, source=source)
    raise ValueError(f"未知的文件分類：{category}（可用值：product, policy）")


def _to_nodes(source: str, category: Category, chunks: list[dict]) -> list[TextNode]:
    nodes = []
    for i, c in enumerate(chunks):
        node = TextNode(
            text=c["text"],
            id_=f"{source}-{i}",
            metadata={
                "source": c["source"],
                "topic": c["topic"],
                "category": c["category"],
                "product_id": c["product_id"],
                # 存 parser 分類（product/policy），update_document 不需要呼叫端重新指定分類，
                # 從既有 chunk 的這個欄位查回來即可（見 get_document_category()）
                "doc_category": category,
            },
        )
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=source)
        nodes.append(node)
    return nodes


def add_document(source: str, category: Category, raw_text: str, index: VectorStoreIndex) -> int:
    """解析文件內容為 chunk，包成帶 ref_doc_id 的 TextNode 灌進索引。回傳新增的 chunk 數。"""
    chunks = _parse(category, raw_text, source)
    nodes = _to_nodes(source, category, chunks)
    if nodes:
        index.insert_nodes(nodes)
    return len(nodes)


def delete_document(source: str, index: VectorStoreIndex) -> None:
    """刪除該文件（ref_doc_id）底下的所有 chunk。"""
    index.delete_ref_doc(source, delete_from_docstore=True)


def update_document(source: str, category: Category, raw_text: str, index: VectorStoreIndex) -> int:
    """刪除舊 chunk 後重新解析、插入新 chunk（不做差異比對）。回傳新增的 chunk 數。"""
    delete_document(source, index)
    return add_document(source, category, raw_text, index)


def _table_full_name() -> str:
    # 見檔案頂端說明：實體資料表名稱是 "data_<table_name>"，schema_name 固定用 public
    # （PGVectorStore.from_params 預設 schema_name="public"，本專案沒有另外指定）。
    return f"public.data_{settings.RAG_PG_TABLE.lower()}"


def _get_engine():
    url = (
        f"postgresql+psycopg2://{settings.RAG_PG_USER}:{settings.RAG_PG_PASSWORD}"
        f"@{settings.RAG_PG_HOST}:{settings.RAG_PG_PORT}/{settings.RAG_PG_DATABASE}"
    )
    return create_engine(url)


def list_documents() -> list[dict]:
    """
    列出所有文件（doc_id/category/chunk_count）。LlamaIndex 沒有現成的「列出所有文件」API，
    直接對 pgvector 的底層 table 下 SQL，用 metadata_->>'doc_id' 分組。
    """
    table = _table_full_name()
    sql = sql_text(
        f"""
        SELECT metadata_->>'doc_id' AS doc_id,
               metadata_->>'doc_category' AS category,
               count(*) AS chunk_count
        FROM {table}
        WHERE metadata_->>'doc_id' IS NOT NULL AND metadata_->>'doc_id' != 'None'
        GROUP BY metadata_->>'doc_id', metadata_->>'doc_category'
        ORDER BY doc_id
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [
        {"doc_id": row.doc_id, "category": row.category or "policy", "chunk_count": row.chunk_count}
        for row in rows
    ]


def get_document_category(source: str) -> Optional[str]:
    """查詢既有文件目前存的 parser 分類（product/policy），供更新 API 不用重新指定分類。"""
    table = _table_full_name()
    sql = sql_text(
        f"""
        SELECT metadata_->>'doc_category' AS category
        FROM {table}
        WHERE metadata_->>'doc_id' = :doc_id
        LIMIT 1
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"doc_id": source}).fetchone()
    return row.category if row else None


def _count_rows() -> int:
    table = _table_full_name()
    engine = _get_engine()
    with engine.connect() as conn:
        return conn.execute(sql_text(f"SELECT count(*) FROM {table}")).scalar_one()


def seed_if_empty(index: VectorStoreIndex) -> None:
    """
    服務啟動時，如果 pgvector table 是空的（例如第一次接上新資料庫），把現有 app/data/*.md
    知識庫內容灌進去，讓既有內容遷移到 pgvector；一次性、冪等（table 有資料後就不會再跑）。

    PGVectorStore 的實體資料表是 lazy 建立的（第一次 insert_nodes/query 時才會觸發
    perform_setup 建表），全新資料庫在任何操作前直接查表會是「table 不存在」而不是「筆數 0」，
    這裡當成「視同空表」處理即可，交給後面的 add_document() 觸發建表。
    """
    try:
        if _count_rows() > 0:
            return
    except Exception:
        pass

    for seed in get_seed_sources():
        raw_text = seed["path"].read_text(encoding="utf-8")
        add_document(seed["source"], seed["category"], raw_text, index)
