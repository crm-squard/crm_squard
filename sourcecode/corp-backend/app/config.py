import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    應用程式設定類別，從環境變數或 .env 檔案載入設定。
    """
    APP_NAME: str = "Corp Backend API"
    ENV: str = "development"
    PORT: int = 8001
    API_V1_STR: str = "/api/v1"

    # GCP & Firebase 設定
    GCP_PROJECT_ID: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None

    # 產品圖片 Storage URL
    PRODUCT_IMAGE_BASE_URL: str = "https://storage.googleapis.com/crm_squard_product_image"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# 建立全域 Settings 實例
settings = Settings()
