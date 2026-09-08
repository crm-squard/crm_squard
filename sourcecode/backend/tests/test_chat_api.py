"""
測試 /api/chat 端點的訂單查詢路徑（main.py 的 _handle_chat，比對 ORDER_CODE_PATTERN 那段）。

用 FastAPI TestClient 當黑箱測試，確保：
- 訊息帶到有效訂單編號時，回傳 type="order" 的結構化格式（code/status/eta/items），
  這個格式前端拿來畫出貨時間軸卡片，不能被破壞。
- 訊息帶到查無此訂單的編號時，依 main.py 目前實際的邏輯回傳 type="text" 的提示訊息
  （不是 404、不是丟例外），並包含訂單編號方便使用者確認。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app, _request_log
from tests.conftest import SEED_ORDERS, NON_EXISTENT_ORDER_CODE


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """避免同一支測試檔案內多次呼叫 /api/chat 時，被 main.py 的簡易 rate limit 誤擋。"""
    _request_log.clear()
    yield
    _request_log.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_chat_with_valid_order_code_returns_order_card(client):
    code = "A12345"
    expected = SEED_ORDERS[code]

    resp = client.post("/api/chat", json={"message": code, "history": [], "provider": "google"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "order"
    assert body["code"] == code
    assert body["status"] == expected["status"]
    assert body["eta"] == expected["eta"]
    assert body["items"] == expected["items"]


def test_chat_with_order_keyword_and_valid_code(client):
    """訊息夾雜文字（含「訂單」二字）也要能解析出正確的訂單編號並回傳一致的結構。"""
    code = "C55210"
    expected = SEED_ORDERS[code]

    resp = client.post(
        "/api/chat",
        json={"message": f"請幫我查一下訂單 {code} 的狀態", "history": [], "provider": "google"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "order"
    assert body["code"] == code
    assert body["status"] == expected["status"]
    assert body["eta"] == expected["eta"]
    assert body["items"] == expected["items"]


def test_chat_with_unknown_order_code_returns_text_message(client):
    """
    依 main.py 目前實際邏輯：找不到訂單時回傳 type="text"，
    text 內容包含查無此訂單的提示與該訂單編號，不是丟 4xx 例外。
    """
    resp = client.post(
        "/api/chat",
        json={"message": NON_EXISTENT_ORDER_CODE, "history": [], "provider": "google"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert body["code"] is None
    assert NON_EXISTENT_ORDER_CODE in body["text"]
    assert "查無訂單編號" in body["text"]


def test_chat_with_order_keyword_but_no_code_prompts_for_code(client):
    """含「訂單」二字但抓不到符合格式的編號時，要提示使用者補訂單編號，而不是當成查無此訂單。"""
    resp = client.post(
        "/api/chat",
        json={"message": "我想查訂單狀態", "history": [], "provider": "google"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert "訂單編號" in body["text"]
