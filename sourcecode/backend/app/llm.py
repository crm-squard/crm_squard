"""
生成模型（LLM）載入：對應提案流程「根據 RAG 查詢結果給 LLM 回答」中的生成端。

provider=local 固定用 MLX + Qwen3.5-2B（見 app/config.py 的 MLX_LLM_MODEL_NAME），
只能在 Apple Silicon（M 系列晶片）上跑，吃 Mac 的 Metal GPU 加速。正式環境（Cloud Run，
x86 Linux）固定用線上 provider（Claude/GPT/Gemini/Grok，見 app/providers.py），
不會呼叫到這個模組——provider=local 只給本機開發用。

這裡不再支援 CPU/transformers 這條路：本來用的 openbmb/MiniCPM5-2B 已經拿掉（它在
Apple Silicon 的 MPS 上會直接 segfault，且它要求的 transformers>=5.6 會跟其他想接的
套件版本衝突），沒有 GPU 加速就直接不提供本地 LLM，不用 CPU 硬跑。

模型只在第一次呼叫時載入（lazy loading），第一次呼叫 /api/chat（provider=local）
會需要等待下載與載入模型。mlx-lm 是選用依賴（見 requirements-mlx.txt）：在非 Apple
Silicon 機器上、或沒安裝 mlx-lm 時呼叫 generate() 會丟出清楚的錯誤，被 /api/chat
的例外處理接住、回傳「系統暫時發生錯誤」，不會讓整個服務掛掉（見 app/main.py 的
_handle_chat()）——這也是為什麼正式環境本來就不該讓使用者選 provider=local。
"""
import platform
import threading

from app.config import settings

_tokenizer = None
_model = None
_opencc_converter = None

# 同一顆模型不管是「產品問答」還是「當日提問摘要」都會用到，
# 用同一把鎖讓所有 LLM 生成請求排隊，避免併發搶 GPU。
_generation_lock = threading.Lock()


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def get_llm():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    if not _is_apple_silicon():
        raise RuntimeError(
            "provider=local 只支援 Apple Silicon（MLX），這台機器不是 Apple Silicon，"
            "請改用線上 provider（anthropic/openai/google/xai）。"
        )

    from mlx_lm import load as mlx_load

    model, tokenizer = mlx_load(settings.MLX_LLM_MODEL_NAME)
    _tokenizer, _model = tokenizer, model
    return _tokenizer, _model


def _get_opencc():
    global _opencc_converter
    if _opencc_converter is None:
        from opencc import OpenCC

        # s2twp：簡體轉繁體（台灣正體，含慣用詞轉換，例如「用户」→「使用者」而不只是簡轉繁的字形）
        _opencc_converter = OpenCC("s2twp")
    return _opencc_converter


def generate(messages: list[dict], max_new_tokens: int = 512) -> str:
    """給定 chat messages（[{role, content}]），跑一次 LLM 生成並回傳文字。"""
    tokenizer, model = get_llm()

    from mlx_lm import generate as mlx_generate

    # enable_thinking=False：Qwen3.5 支援用這個 chat template 參數關掉內部思考過程，
    # 直接輸出答案，避免推理模式那種「先想很久再答」拖慢回應時間；模型不支援這個參數的話
    # tokenizer 會忽略未知的 template kwargs，不會出錯。
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    with _generation_lock:
        output = mlx_generate(model, tokenizer, prompt, max_tokens=max_new_tokens)

    # 保險：就算 enable_thinking=False 沒生效或換成別的推理模型，只要輸出裡還是有
    # <think>...</think>，一律只取 </think> 之後的部分當答案，避免內部思考內容外洩。
    if "</think>" in output:
        output = output.rsplit("</think>", 1)[1].strip()

    # 本地模型偶爾還是會輸出簡體字，這裡統一做簡轉繁（台灣用語）後處理；
    # 對本來就是繁體的輸出幾乎是 no-op，不會有副作用。
    return _get_opencc().convert(output)
