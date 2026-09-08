"""
生成模型（LLM）載入：對應提案流程「根據 RAG 查詢結果給 LLM 回答」中的生成端。

本地模型固定用 openbmb/MiniCPM5-2B，CPU 也可執行（速度較慢），不需要 bitsandbytes。
這顆是「混合推理」模型，同一顆權重可以用 enable_thinking 開關切換要不要輸出
<think>...</think> 內部思考過程；這裡預設關閉（直接回答），避免像純推理模型那樣
思考太長、拖慢回應時間。

模型只在第一次呼叫時載入（lazy loading），第一次呼叫 /api/chat 會需要等待下載與載入模型。

torch/transformers 只在這個模組實際被呼叫（get_llm()/generate()）時才 import，
而不是在模組載入時就 import——這樣線上 API only 的部署（例如沒裝 requirements-local-llm.txt）
只要不觸發本地模型這條路，就不會因為缺少 torch/transformers 而在啟動時就掛掉，
只有真的呼叫到本地模型時才會噴 ImportError。
"""
import threading

from app.config import settings

_tokenizer = None
_model = None
_opencc_converter = None

# 同一顆模型不管是「產品問答」還是「當日提問摘要」都會用到，
# 用同一把鎖讓所有 LLM 生成請求排隊，避免併發搶 CPU/GPU。
_generation_lock = threading.Lock()


def get_llm():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    # device_map="auto" 會用 accelerate 猜測可用記憶體來分配裝置，
    # 在沒有 CUDA 的機器上常會誤判、把部分權重 offload 到硬碟（跑起來極慢甚至出錯）。
    # 明確指定裝置可以避免這個問題。
    #
    # 注意：openbmb/MiniCPM5-2B 在 Apple Silicon 的 MPS 上會直接 segfault（不管
    # float16 還是 float32 都一樣，實測驗證過，Python try/except 也接不住，整個
    # process 直接死掉），所以這裡刻意跳過 MPS、退回 CPU。之後如果換其他本地小模型，
    # 要重新測一次這台機器的 MPS 相容性，不要照抄這個判斷式。
    if torch.cuda.is_available():
        device, dtype = "cuda", torch.float16
    else:
        device, dtype = "cpu", torch.float32

    model_name = settings.LLM_MODEL_NAME
    # trust_remote_code=True：這個模型（openbmb/MiniCPM5-2B）用自訂架構程式碼，
    # 官方要求加這個參數才能載入；代價是會執行該 HF repo 裡的 Python 程式碼，
    # 是刻意的供應鏈信任決定，不是隨便所有模型都該加。
    _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map={"": device},
        trust_remote_code=True,
    )

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

    # enable_thinking=False：MiniCPM5-2B 支援用這個 chat template 參數關掉內部思考過程，
    # 直接輸出答案，避免推理模式那種「先想很久再答」拖慢回應時間；模型不支援這個參數的話
    # （例如 Qwen）transformers 會忽略未知的 template kwargs，不會出錯。
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with _generation_lock:
        output_ids = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
    output = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # 保險：就算 enable_thinking=False 沒生效或換成別的推理模型，只要輸出裡還是有
    # <think>...</think>，一律只取 </think> 之後的部分當答案，避免內部思考內容外洩。
    if "</think>" in output:
        output = output.rsplit("</think>", 1)[1].strip()

    # 本地模型（MiniCPM5 等中國團隊訓練的模型）預設常輸出簡體字，這裡統一做簡轉繁
    # （台灣用語）後處理；對本來就是繁體的輸出（例如 Qwen）幾乎是 no-op，不會有副作用。
    return _get_opencc().convert(output)
