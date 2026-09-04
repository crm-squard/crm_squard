"""
線上 Embedding 模組：使用 Google Gemini API (models/gemini-embedding-001) 進行向量化。

- embed_passages_online(texts) -> 批次為文件段落生成向量 (task_type="retrieval_document")
- embed_query_online(text)     -> 為使用者查詢生成向量 (task_type="retrieval_query")
"""
import os
import json
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError
from app.config import settings

_api_key_cached = None


def get_gemini_api_key() -> str:
    global _api_key_cached
    if _api_key_cached:
        return _api_key_cached

    # 1. 優先從環境變數 GEMINI_API_KEY 讀取
    key = os.getenv("GEMINI_API_KEY")
    if key:
        _api_key_cached = key
        return key

    # 2. 次要從 llm_keys.json 讀取
    try:
        if os.path.exists(settings.LLM_KEYS_PATH):
            with open(settings.LLM_KEYS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("google", {}).get("api_key")
                if key:
                    _api_key_cached = key
                    return key
    except Exception:
        pass

    raise ValueError(
        "未找到 GEMINI_API_KEY。請在 .env 中設定 GEMINI_API_KEY 或在 backend/llm_keys.json 中設定 google.api_key。"
    )


def _init_genai():
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)


def embed_passages_online(texts: list[str]) -> list[list[float]]:
    """為文件段落生成 Gemini 向量，支援自動重試與速率限制處置。"""
    _init_genai()
    if not texts:
        return []

    batch_size = 5
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        for attempt in range(10):
            try:
                result = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=chunk,
                    task_type="retrieval_document",
                )
                all_embeddings.extend(result["embedding"])
                time.sleep(2)  # 控速避免觸發免費版 100 RPM 上限
                break
            except Exception as e:
                if attempt == 9:
                    raise
                print(f"[Embedding Online] Rate limit encountered, retrying in 10s... (attempt {attempt+1}/10)")
                time.sleep(10)

    return all_embeddings


def embed_query_online(text: str) -> list[float]:
    """為使用者查詢生成 Gemini 向量。"""
    _init_genai()
    for attempt in range(10):
        try:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            if attempt == 9:
                raise
            time.sleep(6)


