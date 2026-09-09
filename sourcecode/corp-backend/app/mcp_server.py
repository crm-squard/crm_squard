"""
MCP server：把訂單 CRUD 包成 MCP tools，給 backend（CRM 聊天客服）當 MCP client 呼叫。

跟 app/routers/orders.py 共用同一個 app/crud.py，這裡不重複實作 Firestore 存取邏輯，
只是換一層 MCP tool 介面；REST API 維持原樣、兩條路徑並存。

用 stateless HTTP transport：v1（mcp==1.30.0）時 stateless_http/streamable_http_path
是 FastMCP 建構子參數，v2（mcp==2.0.0b2）的 MCPServer 建構子不再接受這些參數，
改成在 app/main.py 呼叫 mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, ...)
時才指定；"/" 一樣是因為 mount 到 FastAPI 時已經在 app/main.py 指定了 "/mcp" 前綴，
避免變成 "/mcp/mcp"。

錯誤處理：v1 時工具內部 raise 一般例外（RuntimeError），FastMCP 框架會接住並轉成
CallToolResult(is_error=True, ...) 回給 client，不會變成協定層級的錯誤。v2 的 MCPServer
（mcp/server/mcpserver/server.py 內部 call_tool 分派邏輯）行為相同：只有工具內主動
raise mcp.shared.exceptions.MCPError 才會被原樣往外拋成協定層級的 JSON-RPC 錯誤，
一般 Exception 一樣會被接住包成 is_error=True 的 CallToolResult。這裡選擇全面改成
raise MCPError，讓 backend 端可以用 try/except MCPError 明確分辨「工具執行失敗」
（已知的業務錯誤，例如 Firestore 讀寫失敗、找不到訂單、未帶更新欄位），跟連線失敗這種
更底層的例外分開處理；同時仍保留錯誤訊息附掛 log。
"""
import logging

from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import INTERNAL_ERROR, INVALID_PARAMS

from app import crud
from app.schemas import OrderCreate, OrderUpdate

logger = logging.getLogger("corp-backend.mcp")

COLLECTION_ORDERS = "Order"

mcp = MCPServer(name="corp-backend-orders")


@mcp.tool()
def get_order(order_id: str) -> dict | None:
    """依 ID（NewOrderID 或 OrderID）查詢單筆訂單，回應格式同 GET /Order/{order_id}。找不到時回傳 None。"""
    try:
        doc = crud.get_document(collection_name=COLLECTION_ORDERS, doc_id=order_id)
    except Exception as e:
        logger.error(f"MCP get_order 讀取 Firebase 訂單失敗: {e}")
        raise MCPError(code=INTERNAL_ERROR, message=f"讀取 Firebase 訂單失敗: {order_id}") from e
    if not doc:
        return None
    return {"id": doc.id, **doc.data}


@mcp.tool()
def list_orders(limit: int = 100, order_by: str | None = None) -> dict:
    """查詢訂單列表，回應格式同 GET /Order（count + orders）。"""
    try:
        raw_res = crud.list_documents(collection_name=COLLECTION_ORDERS, limit=limit, order_by=order_by)
    except Exception as e:
        logger.error(f"MCP list_orders 查詢 Firebase 訂單列表失敗: {e}")
        raise MCPError(code=INTERNAL_ERROR, message="查詢 Firebase 訂單列表失敗") from e
    orders = [{"id": doc.id, **doc.data} for doc in raw_res.documents]
    return {"count": len(orders), "orders": orders}


@mcp.tool()
def create_order(payload: OrderCreate) -> dict:
    """新增訂單，回應格式同 POST /Order。"""
    try:
        doc_id = payload.NewOrderID or str(payload.OrderID)
        res = crud.create_document(collection_name=COLLECTION_ORDERS, data=payload.model_dump(), doc_id=doc_id)
    except Exception as e:
        logger.error(f"MCP create_order 寫入 Firebase 訂單失敗: {e}")
        raise MCPError(code=INTERNAL_ERROR, message="寫入 Firebase 訂單失敗") from e
    return {"id": res.id, **res.data}


@mcp.tool()
def update_order(order_id: str, payload: OrderUpdate) -> dict | None:
    """更新訂單部分欄位，回應格式同 PATCH /Order/{order_id}。找不到時回傳 None。"""
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise MCPError(code=INVALID_PARAMS, message="未傳遞任何需要更新的欄位")
    try:
        res = crud.update_document(collection_name=COLLECTION_ORDERS, doc_id=order_id, data=update_data, merge=True)
    except Exception as e:
        logger.error(f"MCP update_order 更新 Firebase 訂單失敗: {e}")
        raise MCPError(code=INTERNAL_ERROR, message=f"更新 Firebase 訂單失敗: {order_id}") from e
    if not res:
        return None
    return {"id": res.id, **res.data}


@mcp.tool()
def delete_order(order_id: str) -> dict | None:
    """刪除訂單，回應格式同 DELETE /Order/{order_id}。找不到時回傳 None。"""
    try:
        success = crud.delete_document(collection_name=COLLECTION_ORDERS, doc_id=order_id)
    except Exception as e:
        logger.error(f"MCP delete_order 刪除 Firebase 訂單失敗: {e}")
        raise MCPError(code=INTERNAL_ERROR, message=f"刪除 Firebase 訂單失敗: {order_id}") from e
    if not success:
        return None
    return {"status": "success", "message": f"已成功刪除 Firebase 訂單 ID '{order_id}'"}
