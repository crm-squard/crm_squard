"""
測試 app/orders.py 的 get_order()。

get_order() 現在是 async：先透過 MCP（Streamable HTTP transport）呼叫 corp-backend
的 get_order tool，corp-backend 連不上或查詢失敗時，退回本機 orders.db（SQLite）查詢。

這裡的測試在 corp-backend 沒有啟動的情況下跑（CI／本機開發預設沒有另外起 corp-backend），
所以 MCP 呼叫一定會失敗、驗證的實際上是 fallback 路徑；並用 orders.db 既有的範例資料
（見 SEED_ORDERS，唯讀查詢，不會寫入，安全可重複執行）確認 fallback 結果正確。
"""
import pytest

from app.orders import get_order
from tests.conftest import SEED_ORDERS, NON_EXISTENT_ORDER_CODE


async def test_get_order_returns_existing_order_fields():
    code = "A12345"
    expected = SEED_ORDERS[code]

    order = await get_order(code)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


async def test_get_order_is_case_insensitive():
    """SQLite fallback 內部用 code.upper() 比對，確認小寫輸入也查得到。"""
    code = "b98231"
    expected = SEED_ORDERS["B98231"]

    order = await get_order(code)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


async def test_get_order_returns_none_for_unknown_code():
    order = await get_order(NON_EXISTENT_ORDER_CODE)

    assert order is None


async def test_get_order_falls_back_to_sqlite_when_mcp_unavailable(monkeypatch):
    """corp-backend／MCP 連不上時（例如 ConnectionError），仍要 fallback 回 SQLite 查到正確結果。"""
    import app.orders as orders_module

    async def _raise_connection_error(code):
        raise ConnectionError("corp-backend MCP endpoint 連不上")

    monkeypatch.setattr(orders_module, "_get_order_via_mcp", _raise_connection_error)

    code = "C55210"
    expected = SEED_ORDERS[code]

    order = await get_order(code)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]
