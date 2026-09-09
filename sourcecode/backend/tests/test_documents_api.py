"""
測試 /api/admin/documents 系列端點（新增/查詢/更新/刪除知識庫文件）。

這幾支 API 目前只支援 RAG_ENGINE=llamaindex（pgvector 儲存），需要本機真的起一個
pgvector 服務（見 backend/README.md 的 docker run 指令）並在 .env 設定對應的
RAG_PG_* 連線資訊，跑這份測試前請確認 pgvector 已啟動、能連得上，否則會直接失敗
（不像訂單查詢有 fallback 機制可以在沒有外部服務時仍然通過）。

用一個獨立、不會跟既有知識庫文件撞名的 source（TEST_DOC_ID）測試完整生命週期，
並在測試結束後主動刪除，避免污染共用的 pgvector table。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app, _request_log

TEST_DOC_ID = "pytest_test_doc.md"


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _request_log.clear()
    yield
    _request_log.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        # 測試後清乾淨，避免留下測試資料污染共用的 pgvector table
        c.delete(f"/api/admin/documents/{TEST_DOC_ID}")


def test_create_list_update_delete_document_lifecycle(client):
    # 1. 新增
    create_resp = client.post(
        "/api/admin/documents",
        json={
            "source": TEST_DOC_ID,
            "category": "policy",
            "content": "# Pytest 測試文件\n\n## 測試小節\n這是 pytest 建立的測試內容。\n",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["doc_id"] == TEST_DOC_ID
    assert created["category"] == "policy"
    assert created["chunk_count"] == 1

    # 2. 重複新增同一個 doc_id 要回 409，不能覆蓋
    dup_resp = client.post(
        "/api/admin/documents",
        json={"source": TEST_DOC_ID, "category": "policy", "content": "x"},
    )
    assert dup_resp.status_code == 409

    # 3. 列表看得到剛新增的文件
    list_resp = client.get("/api/admin/documents")
    assert list_resp.status_code == 200
    doc_ids = [d["doc_id"] for d in list_resp.json()["documents"]]
    assert TEST_DOC_ID in doc_ids

    # 4. 更新內容（body 不用帶 category，沿用既有分類）
    update_resp = client.put(
        f"/api/admin/documents/{TEST_DOC_ID}",
        json={"content": "# Pytest 測試文件\n\n## 測試小節\n更新後的內容。\n"},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["doc_id"] == TEST_DOC_ID
    assert updated["category"] == "policy"
    assert updated["chunk_count"] == 1

    # 5. 刪除
    delete_resp = client.delete(f"/api/admin/documents/{TEST_DOC_ID}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"status": "deleted", "doc_id": TEST_DOC_ID}

    # 6. 刪除後列表查不到
    list_resp_after = client.get("/api/admin/documents")
    doc_ids_after = [d["doc_id"] for d in list_resp_after.json()["documents"]]
    assert TEST_DOC_ID not in doc_ids_after


def test_update_nonexistent_document_returns_404(client):
    resp = client.put(
        "/api/admin/documents/does_not_exist.md",
        json={"content": "x"},
    )
    assert resp.status_code == 404


def test_delete_nonexistent_document_returns_404(client):
    resp = client.delete("/api/admin/documents/does_not_exist.md")
    assert resp.status_code == 404
