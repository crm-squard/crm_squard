"""
測試 /api/chat 端點的訂單查詢路徑（main.py 的 _handle_chat，比對 ORDER_CODE_PATTERN 那段）。

用 FastAPI TestClient 當黑箱測試，確保：
- 訊息帶到有效訂單編號時，回傳 type="order" 的結構化格式（code/status/eta/items），
  這個格式前端拿來畫出貨時間軸卡片，不能被破壞。
- 訊息帶到查無此訂單的編號時，依 main.py 目前實際的邏輯回傳 type="text" 的提示訊息
  （不是 404、不是丟例外），並包含訂單編號方便使用者確認。
- 訂單查詢改用公司自訂的 mcp_url（見 app/orders.py、app/main.py）：company_id（也就是
  X-Client-ID header）對不到任何公司、或公司沒填 mcp_url 時，直接回覆「尚未提供訂單查詢
  功能」的文字，不會落到本機 SQLite demo 資料（那是全域資料，跟任何一家真的公司無關）；
  只有公司有填 mcp_url 才會走原本的 MCP／SQLite fallback 邏輯。這裡的測試在 corp-backend
  沒有啟動的情況下跑，所以「有 mcp_url」的情境驗證的實際上也是 SQLite fallback 路徑。
"""
import pytest
from fastapi.testclient import TestClient

from app import accounts_store
from app.config import settings
from app.main import app, _request_log
from tests.conftest import SEED_ORDERS, NON_EXISTENT_ORDER_CODE

CLIENT_HEADERS = {"X-Client-ID": "client_test"}


@pytest.fixture
def order_company():
    """有填 mcp_url 的測試公司，用來驗證「公司有開訂單查詢功能」的路徑。
    mcp_url 指向一個不存在的位址即可——這裡驗證的重點是「有沒有嘗試查詢並 fallback」，
    不是真的接到 corp-backend（corp-backend 沒有另外啟動）。"""
    company = accounts_store.create_company(
        "Pytest Order Company", "http://localhost:9/mcp"
    )
    yield company
    accounts_store.delete_company(company["id"])


def _client_headers(company_id: str) -> dict:
    return {"X-Client-ID": company_id}


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


def test_chat_with_valid_order_code_returns_order_card(client, order_company):
    code = "A12345"
    expected = SEED_ORDERS[code]

    resp = client.post(
        "/api/chat",
        json={"message": code, "history": [], "provider": "google"},
        headers=_client_headers(order_company["id"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "order"
    assert body["code"] == code
    assert body["status"] == expected["status"]
    assert body["eta"] == expected["eta"]
    assert body["items"] == expected["items"]


def test_chat_with_order_keyword_and_valid_code(client, order_company):
    """訊息夾雜文字（含「訂單」二字）也要能解析出正確的訂單編號並回傳一致的結構。"""
    code = "C55210"
    expected = SEED_ORDERS[code]

    resp = client.post(
        "/api/chat",
        json={"message": f"請幫我查一下訂單 {code} 的狀態", "history": [], "provider": "google"},
        headers=_client_headers(order_company["id"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "order"
    assert body["code"] == code
    assert body["status"] == expected["status"]
    assert body["eta"] == expected["eta"]
    assert body["items"] == expected["items"]


def test_chat_with_unknown_order_code_returns_text_message(client, order_company):
    """
    依 main.py 目前實際邏輯：找不到訂單時回傳 type="text"，
    text 內容包含查無此訂單的提示與該訂單編號，不是丟 4xx 例外。
    """
    resp = client.post(
        "/api/chat",
        json={"message": NON_EXISTENT_ORDER_CODE, "history": [], "provider": "google"},
        headers=_client_headers(order_company["id"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert body["code"] is None
    assert NON_EXISTENT_ORDER_CODE in body["text"]
    assert "查無訂單編號" in body["text"]


def test_chat_with_order_code_but_no_company_returns_not_supported_message(client):
    """
    X-Client-ID 對不到任何公司（例如 widget 沒串接真的 company_id，或本測試檔預設的
    "client_test" 不是合法 UUID）時，訂單查詢要回覆「尚未提供」的文字，不能落到 SQLite
    demo 資料裝作查得到——即使輸入的是 SEED_ORDERS 裡真的存在的編號。
    """
    resp = client.post(
        "/api/chat",
        json={"message": "A12345", "history": [], "provider": "google"},
        headers=CLIENT_HEADERS,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert "尚未提供訂單查詢功能" in body["text"]


def test_chat_with_order_code_but_company_has_no_mcp_url_returns_not_supported_message(
    client, test_company
):
    """company_id 查得到公司，但該公司沒填 mcp_url：一樣視為沒開這個功能。"""
    resp = client.post(
        "/api/chat",
        json={"message": "A12345", "history": [], "provider": "google"},
        headers=_client_headers(test_company["id"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert "尚未提供訂單查詢功能" in body["text"]


def test_chat_with_order_keyword_but_no_code_prompts_for_code(client):
    """含「訂單」二字但抓不到符合格式的編號時，要提示使用者補訂單編號，而不是當成查無此訂單。"""
    resp = client.post(
        "/api/chat",
        json={"message": "我想查訂單狀態", "history": [], "provider": "google"},
        headers=CLIENT_HEADERS,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "text"
    assert "訂單編號" in body["text"]


@pytest.mark.parametrize("path", ["/api/providers", "/api/widget/config"])
def test_widget_get_endpoints_require_client_id(client, path):
    resp = client.get(path)

    assert resp.status_code == 422
    assert "X-Client-ID" in resp.json()["detail"]


def test_chat_rejects_too_long_client_id(client):
    resp = client.post(
        "/api/chat",
        json={"message": "我想查訂單狀態", "history": [], "provider": "google"},
        headers={"X-Client-ID": "x" * 129},
    )

    assert resp.status_code == 422


def test_widget_config_returns_customizable_defaults(client):
    resp = client.get("/api/widget/config", headers=CLIENT_HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {
        "brandName": "線上客服",
        "welcomeMessage": "您好，我是線上客服，可以問我任何產品的規格、特色，或是輸入訂單編號查詢配送狀態喔。",
        "logoUrl": None,
        "theme": {
            "primaryColor": "#315b7d",
            "surfaceColor": "#ffffff",
            "textColor": "#17212b",
            "borderRadius": 20,
        },
    }


def test_widget_client_header_is_allowed_by_cors(client):
    allowed_origin = "https://example.com" if "*" in settings.CORS_ORIGINS else settings.CORS_ORIGINS[0]
    resp = client.options(
        "/api/chat",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-Client-ID",
        },
    )

    assert resp.status_code == 200
    assert "x-client-id" in resp.headers["access-control-allow-headers"].lower()
