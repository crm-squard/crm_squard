"""
文檔管理核心邏輯：新增/刪除/更新/列出 pgvector（llamaindex 引擎）裡的知識庫文件。

架構：doc_id 完全內部化，只存在這個模組跟資料庫裡，對外一律用「路徑」溝通。
- kb_documents：內容身分，content_hash（SHA256）是唯一依據，判斷「是不是同一份內容」。
- kb_document_labels：路徑/標籤，doc_id 是一般外鍵（可重複）——一份內容可以同時掛在
  多個路徑底下，各自路徑有各自的標籤，互不影響、也不會重複存向量（一對多）。
- pgvector 的向量/chunk 儲存交給 LlamaIndex 的 PGVectorStore 全權處理，這個模組只負責
  「文件身分該怎麼管理」，不碰它的表結構；chunk 的 ref_doc_id 統一用 kb_documents.doc_id
  （流水號字串化），不是路徑本身，所以改路徑（見 upsert_document 的 linked 情境）完全不用
  碰到任何一筆向量。

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
   不是 "kb_chunks" 本身；_count_rows() 這裡要直接對實體表下 SQL，必須對齊這個命名規則。
"""
import hashlib
import re
from typing import Callable, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode
from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine, URL

from app.config import settings
from app.documents import get_seed_sources
from app.rag.product_parser import parse_products

Parser = Callable[[str, str], list[dict]]


def hash_content(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


# 通用 markdown 拆分邏輯：依 H1（文件標題）/H2（小節標題）切段落，每個 H2 小節是一個 chunk。
# 管理頁面上傳的文件一律用這個 parser；產品種子文件因為有固定的規格條列格式，seed_if_empty()
# 改用 product_parser.parse_products 保留逐條拆分的檢索精準度（見該檔案開頭說明）。
_GENERIC_H1_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_GENERIC_H2_SPLIT_PATTERN = re.compile(r"(^##\s+.+$)", re.MULTILINE)


def parse_generic_markdown(raw_text: str, source: str) -> list[dict]:
    """依 H1/H2 切段落。chunk 內部 category 欄位固定給空字串——這是展示用的舊欄位，
    新流程不再用「分類」這個概念，跟文件身分的 tags 是不同語意，不要混用。"""
    h1_match = _GENERIC_H1_PATTERN.search(raw_text)
    doc_title = h1_match.group(1).strip() if h1_match else source

    parts = _GENERIC_H2_SPLIT_PATTERN.split(raw_text)
    chunks = []
    for i in range(1, len(parts), 2):
        section_title = parts[i].lstrip("#").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if not body:
            continue
        chunks.append({
            "text": f"{doc_title}－{section_title}：\n{body}",
            "source": source,
            "topic": f"{doc_title}：{section_title}",
            "category": "",
            "product_id": "",
        })
    return chunks


def _build_nodes(ref_doc_id: str, display_source: str, chunks: list[dict]) -> list[TextNode]:
    """
    把解析出來的 chunk 包成帶 ref_doc_id 的 TextNode。ref_doc_id 是 kb_documents.doc_id
    （流水號字串化，管理/刪除用的穩定身分），display_source 是給聊天檢索顯示用的路徑
    （建立當下觸發 embed 的那個路徑，多個路徑共用同一份內容時不會動態更新，只是顯示用途）。
    """
    nodes = []
    for i, c in enumerate(chunks):
        node = TextNode(
            text=c["text"],
            id_=f"{ref_doc_id}-{i}",
            metadata={
                "source": display_source,
                "topic": c["topic"],
                "category": c["category"],
                "product_id": c["product_id"],
            },
        )
        # ref_doc_id 設定方式：TextNode 建構子的 ref_doc_id 參數會被靜默忽略
        # （llama-index-core==0.11.17 沒有這個欄位），必須透過 relationships 設定，
        # 否則 delete_ref_doc() 之後篩不到任何 row。
        node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=ref_doc_id)
        nodes.append(node)
    return nodes


_engine: Optional[Engine] = None
_schema_ready = False


def _get_engine() -> Engine:
    """整個 process 共用同一個 Engine（含連線池），不要每次呼叫都重新建立——這個函式
    呼叫頻率很高（幾乎每支公開函式都會呼叫一次），重複 create_engine() 等於重複開連線池，
    長期跑下去會浪費資源、增加資料庫端的閒置連線數。"""
    global _engine
    if _engine is None:
        # 用 URL.create() 組連線字串（不是手動 f-string 拼接）：Supabase 的 pooler
        # user 名稱帶了「.」（例如 postgres.xxxxx），密碼也可能含特殊字元，URL.create()
        # 會自動做必要的 URL 編碼，手動拼字串遇到這些字元會組出錯誤的連線字串。
        # sslmode=require：Supabase（以及大多數雲端 Postgres）要求 TLS 連線，本機
        # docker pgvector 沒有這個限制但加上通常也相容，不用依環境切換。
        url = URL.create(
            "postgresql+psycopg2",
            username=settings.RAG_PG_USER,
            password=settings.RAG_PG_PASSWORD,
            host=settings.RAG_PG_HOST,
            port=settings.RAG_PG_PORT,
            database=settings.RAG_PG_DATABASE,
            query={"sslmode": "require"},
        )
        _engine = create_engine(url)
    return _engine


def _ensure_schema() -> None:
    """
    確保 kb_documents／kb_document_labels 這兩張身分/標籤表存在。冪等、每個 process
    只會真的執行一次 DDL（用模組層級旗標快取），之後呼叫都是無成本的早退。
    """
    global _schema_ready
    if _schema_ready:
        return
    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS kb_documents (
                doc_id          BIGSERIAL PRIMARY KEY,
                content_hash    CHAR(64) NOT NULL UNIQUE,
                file_size_bytes INTEGER NOT NULL,
                chunk_count     INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ))
        conn.execute(sql_text(
            """
            CREATE TABLE IF NOT EXISTS kb_document_labels (
                id         BIGSERIAL PRIMARY KEY,
                doc_id     BIGINT NOT NULL REFERENCES kb_documents(doc_id) ON DELETE CASCADE,
                path       TEXT NOT NULL UNIQUE,
                tags       TEXT[] NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        ))
        conn.execute(sql_text(
            "CREATE INDEX IF NOT EXISTS kb_document_labels_doc_id_idx ON kb_document_labels (doc_id)"
        ))
    _schema_ready = True


def get_label(path: str) -> Optional[dict]:
    """查這個路徑目前指向哪份內容（doc_id/tags/content_hash/chunk_count），查不到回 None。"""
    _ensure_schema()
    sql = sql_text(
        """
        SELECT l.doc_id, l.tags, d.content_hash, d.chunk_count
        FROM kb_document_labels l JOIN kb_documents d ON d.doc_id = l.doc_id
        WHERE l.path = :path
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"path": path}).fetchone()
    if row is None:
        return None
    return {
        "doc_id": row.doc_id,
        "tags": list(row.tags) if row.tags is not None else [],
        "content_hash": row.content_hash,
        "chunk_count": row.chunk_count,
    }


def find_document_by_hash(content_hash: str) -> Optional[dict]:
    """查這個內容雜湊有沒有既有的 kb_documents 紀錄（不管掛在哪個路徑底下），查不到回 None。"""
    _ensure_schema()
    sql = sql_text("SELECT doc_id, chunk_count FROM kb_documents WHERE content_hash = :h")
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(sql, {"h": content_hash}).fetchone()
    if row is None:
        return None
    return {"doc_id": row.doc_id, "chunk_count": row.chunk_count}


def _relabel_and_collect_orphan(path: str, doc_id: int, tags: list[str], old_doc_id: Optional[int]) -> Optional[int]:
    """
    把路徑指向 doc_id（不存在就新增、存在就整筆覆蓋），跟「舊 doc_id 是否變成孤兒」這兩件事
    都是純 SQL、彼此之間不需要插入任何外部呼叫，包在同一個 transaction 裡一次做完。

    回傳「真的沒人指了、需要清掉向量的 doc_id」；沒有孤兒（or old_doc_id 就是 None／沒變）
    回傳 None。向量刪除本身是外部呼叫（LlamaIndex 自己的連線，不在這個 transaction 裡），
    沒辦法一起原子化，所以拆成兩段：這裡只負責在 SQL 層面「判斷」，真的要刪向量交給呼叫端
    另外呼叫 _finalize_orphan_deletion()。
    """
    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                """
                INSERT INTO kb_document_labels (doc_id, path, tags)
                VALUES (:doc_id, :path, :tags)
                ON CONFLICT (path) DO UPDATE SET doc_id = EXCLUDED.doc_id, tags = EXCLUDED.tags
                """
            ),
            {"doc_id": doc_id, "path": path, "tags": tags},
        )
        if old_doc_id is None or old_doc_id == doc_id:
            return None
        remaining = conn.execute(
            sql_text("SELECT count(*) FROM kb_document_labels WHERE doc_id = :id"), {"id": old_doc_id}
        ).scalar_one()
        return old_doc_id if remaining == 0 else None


def _finalize_orphan_deletion(doc_id: int, index: VectorStoreIndex) -> None:
    """
    真的刪掉一個已經沒人指的 doc_id：先刪向量（外部呼叫），成功後才刪 kb_documents 那筆。
    順序很重要——如果反過來先刪 kb_documents 紀錄，向量刪除又失敗，會留下檢索得到、
    但任何路徑/標籤都查不到來源的「幽靈向量」；現在這個順序最壞情況只是留下一筆沒有
    對應向量、也不會被任何 API 顯示出來的孤兒 kb_documents 紀錄，之後可以再補一支背景
    清理工具處理，不影響現有功能正確性。
    """
    index.delete_ref_doc(str(doc_id), delete_from_docstore=True)
    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM kb_documents WHERE doc_id = :id"), {"id": doc_id})


def _create_document_with_embedding(
    path: str, raw_text: str, index: VectorStoreIndex, parser: Parser = parse_generic_markdown
) -> dict:
    """真的解析＋embed 一份新內容：新增 kb_documents 一筆，插入對應的向量，回傳新 doc_id 與 chunk 數。"""
    encoded = raw_text.encode("utf-8")
    content_hash = hashlib.sha256(encoded).hexdigest()
    engine = _get_engine()
    with engine.begin() as conn:
        doc_id = conn.execute(
            sql_text(
                """
                INSERT INTO kb_documents (content_hash, file_size_bytes, chunk_count)
                VALUES (:h, :s, 0) RETURNING doc_id
                """
            ),
            {"h": content_hash, "s": len(encoded)},
        ).scalar_one()

    chunks = parser(raw_text, path)
    nodes = _build_nodes(str(doc_id), path, chunks)
    if nodes:
        index.insert_nodes(nodes)

    with engine.begin() as conn:
        conn.execute(
            sql_text("UPDATE kb_documents SET chunk_count = :c WHERE doc_id = :id"),
            {"c": len(nodes), "id": doc_id},
        )
    return {"doc_id": doc_id, "chunk_count": len(nodes)}


def upsert_document(
    path: str, tags: list[str], client_sha256: str, raw_text: Optional[str], index: VectorStoreIndex
) -> dict:
    """
    知識庫文件管理的唯一寫入入口：不需要呼叫端提供任何 doc_id，純粹依「路徑」跟「內容雜湊」
    交叉查詢決定要做什麼事。回傳 {"status", "chunk_count", "content_changed"}。

    - 這個路徑本來就指向這個雜湊：標籤沒變 -> unchanged；標籤變了 -> tags_only_changed（不重新 embed）。
    - 這個雜湊命中「別的」既有內容（不管這個路徑本來有沒有紀錄）：linked，只改標籤紀錄指向該內容，
      不重新 embed；如果這個路徑原本指向別的 doc_id，且那個 doc_id 之後沒有任何路徑指著了，順手清掉。
    - 兩者都沒中：真的需要 raw_text 才能新增/更新內容（呼叫端要保證這種情況一定有帶檔案）。
    """
    _ensure_schema()
    label = get_label(path)

    if label is not None and label["content_hash"] == client_sha256:
        if set(label["tags"]) == set(tags):
            return {"status": "unchanged", "chunk_count": label["chunk_count"], "content_changed": False}
        _relabel_and_collect_orphan(path, label["doc_id"], tags, old_doc_id=None)
        return {"status": "tags_only_changed", "chunk_count": label["chunk_count"], "content_changed": False}

    old_doc_id = label["doc_id"] if label is not None else None

    matched = find_document_by_hash(client_sha256)
    if matched is not None:
        orphan = _relabel_and_collect_orphan(path, matched["doc_id"], tags, old_doc_id)
        if orphan is not None:
            _finalize_orphan_deletion(orphan, index)
        return {"status": "linked", "chunk_count": matched["chunk_count"], "content_changed": False}

    if raw_text is None:
        raise ValueError("需要上傳檔案內容才能新增或更新這份文件。")

    created = _create_document_with_embedding(path, raw_text, index)
    orphan = _relabel_and_collect_orphan(path, created["doc_id"], tags, old_doc_id)
    if orphan is not None:
        _finalize_orphan_deletion(orphan, index)
    status = "content_changed" if label is not None else "new"
    return {"status": status, "chunk_count": created["chunk_count"], "content_changed": True}


def list_documents() -> list[dict]:
    """列出所有路徑（一份內容掛兩個路徑就是兩列，各自標籤）。"""
    _ensure_schema()
    sql = sql_text(
        """
        SELECT l.path, l.tags, d.chunk_count, d.file_size_bytes, d.created_at, d.content_hash
        FROM kb_document_labels l JOIN kb_documents d ON d.doc_id = l.doc_id
        ORDER BY l.path
        """
    )
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [
        {
            "path": row.path,
            "tags": list(row.tags) if row.tags is not None else [],
            "chunk_count": row.chunk_count,
            "file_size_bytes": row.file_size_bytes,
            "uploaded_at": row.created_at.isoformat() if row.created_at is not None else None,
            "content_hash": row.content_hash,
        }
        for row in rows
    ]


def list_paths_by_prefix(prefix: str) -> list[str]:
    """列出以 prefix 開頭的所有路徑，用於「資料夾全量覆蓋上傳」比對這次沒包含到的舊路徑。"""
    _ensure_schema()
    sql = sql_text("SELECT path FROM kb_document_labels WHERE path LIKE :pattern")
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, {"pattern": prefix + "%"}).fetchall()
    return [row.path for row in rows]


def delete_document_by_path(path: str, index: VectorStoreIndex) -> bool:
    """刪除這個路徑的標籤紀錄；該內容沒有其他路徑指著了才真的刪掉向量與內容紀錄。"""
    _ensure_schema()
    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            sql_text("DELETE FROM kb_document_labels WHERE path = :path RETURNING doc_id"), {"path": path}
        ).fetchone()
        if row is None:
            return False
        remaining = conn.execute(
            sql_text("SELECT count(*) FROM kb_document_labels WHERE doc_id = :id"), {"id": row.doc_id}
        ).scalar_one()
    if remaining == 0:
        _finalize_orphan_deletion(row.doc_id, index)
    return True


def _table_full_name() -> str:
    # 見檔案頂端說明：實體資料表名稱是 "data_<table_name>"，schema_name 固定用 public
    # （PGVectorStore.from_params 預設 schema_name="public"，本專案沒有另外指定）。
    return f"public.data_{settings.RAG_PG_TABLE.lower()}"


def _count_rows() -> int:
    table = _table_full_name()
    engine = _get_engine()
    with engine.connect() as conn:
        return conn.execute(sql_text(f"SELECT count(*) FROM {table}")).scalar_one()


def seed_if_empty(index: VectorStoreIndex) -> None:
    """
    服務啟動時，如果 pgvector table 是空的（例如第一次接上新資料庫），把現有 app/data/*.md
    知識庫內容灌進去；一次性、冪等（table 有資料後就不會再跑）。跟管理頁面上傳走同一套
    kb_documents／kb_document_labels 身分管理，seed 進來的文件一樣會出現在
    GET /api/admin/documents，路徑固定用檔名、標籤固定用種子分類（product/policy）。

    產品種子文件（規格條列格式）用 product_parser.parse_products 保留逐條拆分的檢索精準度；
    其餘政策文件用通用的 parse_generic_markdown（H1/H2 拆段落，效果等同已淘汰的
    policy_parser.parse_policy_doc，兩者輸出格式相容，不需要保留兩套邏輯）。

    PGVectorStore 的實體資料表是 lazy 建立的（第一次 insert_nodes/query 時才會觸發
    perform_setup 建表），全新資料庫在任何操作前直接查表會是「table 不存在」而不是「筆數 0」，
    這裡當成「視同空表」處理即可，交給後面 _create_document_with_embedding() 觸發建表。
    """
    try:
        if _count_rows() > 0:
            return
    except Exception:
        pass

    for seed in get_seed_sources():
        raw_text = seed["path"].read_text(encoding="utf-8")
        path = seed["source"]
        parser = parse_products if seed["category"] == "product" else parse_generic_markdown
        created = _create_document_with_embedding(path, raw_text, index, parser=parser)
        _relabel_and_collect_orphan(path, created["doc_id"], [seed["category"]], old_doc_id=None)
