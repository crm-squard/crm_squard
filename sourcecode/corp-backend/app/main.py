from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.firebase_client import initialize_firebase
from app.routers import firestore, health, orders

# 設定 Logging 格式與層級
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("corp-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 應用程式生命週期管理：
    - Startup: 初始化 Firebase Admin SDK
    - Shutdown: 資源清理
    """
    logger.info("啟動 Corp Backend FastAPI 服務中...")
    try:
        initialize_firebase()
    except Exception as e:
        logger.warning(f"Startup 時 Firebase 初始化警告: {e}")
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


@app.get("/", summary="首頁說明資訊")
def read_root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/health",
        "api_v1": settings.API_V1_STR
    }
