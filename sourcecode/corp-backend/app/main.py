from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.firebase_client import initialize_firebase
from app.mcp_server import mcp
from app.routers import firestore, health, orders, products

# 設定 Logging 格式與層級
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("corp-backend")

# streamable_http_app() 要先呼叫一次，session_manager 才會被建立起來，
# 後面 lifespan 裡才能透過 mcp.session_manager.run() 啟動它。
#
# v1（FastMCP）時 json_response/stateless_http 是建構子參數；v2（MCPServer）的建構子
# 不再接受這些參數，改成呼叫 streamable_http_app() 時才指定。streamable_http_path="/"
# 是因為下面 app.mount("/mcp", ...) 已經加了 "/mcp" 前綴，避免變成 "/mcp/mcp"。
mcp_asgi_app = mcp.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 應用程式生命週期管理：
    - Startup: 初始化 Firebase Admin SDK、啟動 MCP session manager
    - Shutdown: 資源清理

    Starlette 不會自動把 mount 進來的子 app 的 lifespan 串起來，
    所以 MCP session manager 要在這裡手動 run()，不然 stateless HTTP transport 收不到請求。
    """
    logger.info("啟動 Corp Backend FastAPI 服務中...")
    try:
        initialize_firebase()
    except Exception as e:
        logger.warning(f"Startup 時 Firebase 初始化警告: {e}")
    async with mcp.session_manager.run():
        yield
    logger.info("Corp Backend FastAPI 服務關閉中...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Corp Backend REST API 服務，提供 GCP Firebase Firestore 資料庫之 CRUD 操作與管理介面。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 設定跨來源資源共享 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(health.router)
app.include_router(firestore.router, prefix=settings.API_V1_STR)
app.include_router(orders.router, prefix=settings.API_V1_STR)
app.include_router(products.router, prefix=settings.API_V1_STR)

# MCP server（訂單 CRUD tools），跟上面的 REST API 並存，共用同一份 app/crud.py
#
# 注意：這個端點目前完全沒有身分驗證/授權檢查，任何能連到這個 port 的人都能直接呼叫
# create_order/update_order/delete_order 竄改或刪除 Firestore 正式訂單資料。
# 正式上線前必須加上認證（例如共享密鑰 header）或網路層限制（Cloud Run 內部 ingress + IAM），
# 跟 backend 的 /api/admin/summary 是同一類已知風險，見安全稽核記錄。
app.mount("/mcp", mcp_asgi_app)


@app.get("/", summary="首頁說明資訊")
def read_root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/health",
        "api_v1": settings.API_V1_STR
    }
