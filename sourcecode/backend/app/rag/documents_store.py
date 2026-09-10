"""
文檔管理核心邏輯：新增/刪除/更新/列出 pgvector（llamaindex 引擎）裡的知識庫文件。

不另外保存文件原文：pgvector 的 node 表（chunk 文字 + 向量 + metadata）就是唯一資料來源，
「更新」= 刪除該文件舊 chunk + 插入新 chunk。每份文件的 chunk 都帶同一組文件級 metadata
（content_hash／uploaded_at／file_size_bytes），更新時先比對 content_hash（SHA256），
內容沒變就跳過刪除+重新 embed，避免無謂的向量重算（embedding 是這條路徑裡最貴的操作）。

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
import hashlib
from datetime import datetime, timezone
from typing import Literal, Optional, TypedDict

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from sqlalchemy import create_engine
from sqlalchemy import text as sql_text

from app.config import settings
from app.documents import get_seed_sources
from app.rag.policy_parser import parse_policy_doc
from app.rag.product_parser import parse_products

Category = Literal["product", "policy"]


class DocumentMeta(TypedDict):
    category: str
    content_hash: str
    uploaded_at: str
    file_size_bytes: int


def _parse(category: Category, raw_text: str, source: str) -> list[dict]:
    if category == "product":
        return parse_products(raw_text, source=source)
    if category == "policy":
        return parse_policy_doc(raw_text, source=source)
    raise ValueError(f"未知的文件分類：{category}（可用值：product, policy）")


def hash_content(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def _to_nodes(source: str, category: Category, chunks: list[dict], doc_meta: dict) -> list[TextNode]:
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
                # 從既有 chunk 的這個欄位查回來即可（見 get_document_meta()）
                "doc_category": category,
                **doc_meta,
            },
        )
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=source)
        nodes.append(node)
    return nodes


def add_document(
    source: str, category: Category, raw_text: str, index: VectorStoreIndex
) -> int:
    """
    解析文件內容為 chunk，包成帶 ref_doc_id 的 TextNode 灌進索引。回傳新增的 chunk 數。

    doc_meta（content_hash/uploaded_at/file_size_bytes）在這裡統一計算、存進每個 chunk 的
    metadata：file_size_bytes 用 raw_text 的 UTF-8 位元組數（上傳來源固定是 .md 文字檔，
    這個值等同原始檔案大小，不需要呼叫端額外傳位元組數）。
    """
    encoded = raw_text.encode("utf-8")
    doc_meta = {
        "content_hash": hashlib.sha256(encoded).hexdigest(),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "file_size_bytes": len(encoded),
    }
    chunks = _parse(category, raw_text, source)
    nodes = _to_nodes(source, category, chunks, doc_meta)
    if nodes:
        index.insert_nodes(nodes)
    return len(nodes)


def delete_document(source: str, index: VectorStoreIndex) -> None:
    """刪除該文件（ref_doc_id）底下的所有 chunk。"""
    index.delete_ref_doc(source, delete_from_docstore=True)


def update_document(
    source: str, category: Category, raw_text: str, index: VectorStoreIndex
) -> tuple[int, bool]:
    """
    先比對 SHA256：內容跟既有版本一樣就跳過重新 embed，直接回傳目前的 chunk 數、changed=False。
    內容有變才刪除舊 chunk、重新解析插入新 chunk（連帶更新 uploaded_at/file_size_bytes）。
    回傳 (chunk 數, 是否有真的重新 embed)。
    """
    new_hash = hash_content(raw_text)
    existing = get_document_meta(source)
    if existing is not None and existing["content_hash"] == new_hash:
        return _count_chunks(source), False
    delete_document(source, index)
    return add_document(source, category, raw_text, index), True


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
    列出所有文件（doc_id/category/chunk_count/uploaded_at/file_size_bytes）。LlamaIndex
    沒有現成的「列出所有文件」API，直接對 pgvector 的底層 table 下 SQL，用 metadata_->>'doc_id'
    分組；uploaded_at/file_size_bytes 同一份文件底下每個 chunk 都存一樣的值，取 MAX 即可
    （純粹是「挑一個值」的手段，不是真的要比大小）。
    """
    table = _table_full_name()
    sql = sql_text(
        f"""
        SELECT metadata_->>'doc_id' AS doc_id,
               metadata_->>'doc_category' AS category,
               count(*) AS chunk_count,
               max(metadata_->>'uploaded_at') AS uploaded_at,
               max((metadata_->>'file_size_bytes')::int) AS file_size_bytes
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
        {
            "doc_id": row.doc_id,
            "category": row.category or "policy",
            "chunk_count": row.chunk_count,
            "uploaded_at": row.uploaded_at,
            "file_size_bytes": row.file_size_bytes,
        }
        for row in rows
    ]


def get_document_meta(source: str) -> Optional[DocumentMeta]:
    """查詢既有文件目前存的分類/雜湊/上傳資訊，供新增判重、更新比對、刪除前存在檢查共用。"""
    table = _table_full_name()
    sql = sql_text(
        f"""
        SELECT metadata_->>'doc_category' AS category,
               metadata_->>'content_hash' AS content_hash,
               metadata_->>'uploaded_at' AS uploaded_at,
               (metadata_->>'file_size_bytes')::int AS file_size_bytes
        FROM {table}
        WHERE metadata_->>'doc_id' = :doc_id
        LIMIT 1
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"doc_id": source}).fetchone()
    if row is None:
        return None
    return {
        "category": row.category,
        "content_hash": row.content_hash,
        "uploaded_at": row.uploaded_at,
        "file_size_bytes": row.file_size_bytes,
    }


def find_duplicate_by_hash(content_hash: str, exclude_source: str) -> Optional[str]:
    """
    查有沒有『別的』doc_id 存了一樣的 content_hash（同一份內容被上傳成兩個不同文件）。
    只做提示用，不會擋下新增/更新——找到就回傳那個 doc_id，供 API 層在回應裡提醒管理者。
    """
    table = _table_full_name()
    sql = sql_text(
        f"""
        SELECT metadata_->>'doc_id' AS doc_id
        FROM {table}
        WHERE metadata_->>'content_hash' = :content_hash
          AND metadata_->>'doc_id' != :exclude_source
        LIMIT 1
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"content_hash": content_hash, "exclude_source": exclude_source}).fetchone()
    return row.doc_id if row else None


def _count_chunks(source: str) -> int:
    table = _table_full_name()
    sql = sql_text(f"SELECT count(*) FROM {table} WHERE metadata_->>'doc_id' = :doc_id")
    engine = _get_engine()
    with engine.connect() as conn:
        return conn.execute(sql, {"doc_id": source}).scalar_one()


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
