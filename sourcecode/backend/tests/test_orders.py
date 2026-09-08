"""
測試 app/orders.py 的 get_order()。

get_order() 現在整支都是透過 MCP（stdio transport）呼叫 order_server.py 的
query_order 工具，這裡是真的跑一次 subprocess 往返，驗證整條路徑
（client -> stdio subprocess -> order_server -> _fetch_order_data -> orders.db）
是通的，不是只測到某一層的 mock。

用的是 orders.db 既有的範例資料（唯讀查詢，不會寫入，安全可重複執行）。
"""
from app.orders import get_order
from tests.conftest import SEED_ORDERS, NON_EXISTENT_ORDER_CODE


def test_get_order_returns_existing_order_fields():
    code = "A12345"
    expected = SEED_ORDERS[code]

    order = get_order(code)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


def test_get_order_is_case_insensitive():
    """_fetch_order_data 內部用 code.upper() 比對，確認小寫輸入也查得到。"""
    code = "b98231"
    expected = SEED_ORDERS["B98231"]

    order = get_order(code)

    assert order is not None
    assert order["status"] == expected["status"]
    assert order["eta"] == expected["eta"]
    assert order["items"] == expected["items"]


def test_get_order_returns_none_for_unknown_code():
    order = get_order(NON_EXISTENT_ORDER_CODE)

    assert order is None
