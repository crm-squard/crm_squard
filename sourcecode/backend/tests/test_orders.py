"""
測試 app/orders.py 的 get_order()。

get_order() 現在是 async，且 mcp_url 改為必填參數（呼叫端負責先查出公司有沒有設定，見
app/main.py）：先透過 MCP（Streamable HTTP transport）呼叫該 URL 的 get_order tool，
連不上或查詢失敗時，退回本機 orders.db（SQLite）查詢。

這裡的測試在 corp-backend 沒有啟動的情況下跑（CI／本機開發預設沒有另外起 corp-backend），
所以 MCP 呼叫一定會失敗、驗證的實際上是 fallback 路徑；並用 orders.db 既有的範例資料
（見 SEED_ORDERS，唯讀查詢，不會寫入，安全可重複執行）確認 fallback 結果正確。
mcp_url 本身的值在這些測試裡不重要（反正連不上），固定用一個假的測試用 URL。
"""
import pytest

from app.orders import get_order
from tests.conftest import SEED_ORDERS, NON_EXISTENT_ORDER_CODE

FAKE_MCP_URL = "http://localhost:9/mcp"


async def test_get_order_returns_existing_order_fields():
    code = "A12345"
    expected = SEED_ORDERS[code]

    order = await get_order(code, FAKE_MCP_URL)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


async def test_get_order_is_case_insensitive():
    """SQLite fallback 內部用 code.upper() 比對，確認小寫輸入也查得到。"""
    code = "b98231"
    expected = SEED_ORDERS["B98231"]

    order = await get_order(code, FAKE_MCP_URL)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


async def test_get_order_returns_none_for_unknown_code():
    order = await get_order(NON_EXISTENT_ORDER_CODE, FAKE_MCP_URL)

    assert order is None


async def test_get_order_falls_back_to_sqlite_when_mcp_unavailable(monkeypatch):
    """corp-backend／MCP 連不上時（例如 ConnectionError），仍要 fallback 回 SQLite 查到正確結果。"""
    import app.orders as orders_module

    async def _raise_connection_error(code, mcp_url):
        raise ConnectionError("corp-backend MCP endpoint 連不上")

    monkeypatch.setattr(orders_module, "_get_order_via_mcp", _raise_connection_error)

    code = "C55210"
    expected = SEED_ORDERS[code]

    order = await get_order(code, FAKE_MCP_URL)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


async def test_get_order_via_mcp_is_stateless_and_self_describing(monkeypatch):
    """
    走真正的 MCP 呼叫（進程內的 ASGI server，不需要啟動 corp-backend），驗證無狀態協定：
    不做 initialize 握手、不帶 Mcp-Session-Id，且每個請求自己帶協定版本與 client 資訊／能力，
    這樣任何一台 corp-backend 實例都能單獨處理請求，可以水平擴充。
    """
    import httpx2
    from mcp.client import Client
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server.mcpserver import MCPServer

    import app.orders as orders_module

    fake_corp_backend = MCPServer(name="fake-corp-backend")

    @fake_corp_backend.tool()
    def get_order(order_id: str) -> dict:
        return {"Status": "Shipped", "OrderDate": "2026-09-01", "ProductName": "測試商品"}

    mcp_app = fake_corp_backend.streamable_http_app(streamable_http_path="/", json_response=True, stateless_http=True)
    seen_requests = []

    async def recording_app(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            seen_requests.append({"session_id": headers.get(b"mcp-session-id"), "version": headers.get(b"mcp-protocol-version")})
        await mcp_app(scope, receive, send)

    # Client 要在 async with 裡才會連線，這裡只需要換掉 transport，其餘參數（mode、client_info）照原樣傳入
    def _client_factory(url, **kwargs):
        http_client = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=recording_app))
        captured_kwargs.update(kwargs)
        return Client(streamable_http_client(url, http_client=http_client), **kwargs)

    captured_kwargs = {}
    monkeypatch.setattr(orders_module, "Client", _client_factory)

    async with fake_corp_backend.session_manager.run():
        order = await orders_module._get_order_via_mcp("a12345", "http://localhost:8001/")

    assert order == {"status": 2, "eta": "2026-09-01", "items": "測試商品"}
    assert captured_kwargs["mode"] == "2026-07-28"
    assert seen_requests, "應該至少送出一個 MCP 請求"
    assert all(r["session_id"] is None for r in seen_requests)
    assert all(r["version"] == b"2026-07-28" for r in seen_requests)
