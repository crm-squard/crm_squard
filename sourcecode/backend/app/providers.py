"""
線上付費 LLM 供應商分派層：讓 /api/chat 除了本地 MiniCPM5-2B 模型外，
也能選擇呼叫 Anthropic Claude、OpenAI、Google Gemini、xAI Grok 的線上 API。

API key／要用的模型名稱存在 settings.LLM_KEYS_PATH 指到的 JSON 檔（預設 backend/llm_keys.json，
不進 git，範本在 backend/llm_keys.example.json）。這個檔案跟程式碼分開放，
是因為 key 是機密資料，不該跟一般設定（.env）混在一起，方便單獨管理/排除在版控外。

所有 generate_xxx() 函式吃同一種 messages 格式：[{"role": "system"|"user"|"assistant", "content": str}]，
跟本地模型（app/llm.py 的 generate()）介面一致，agent.py 呼叫時不需要知道背後是哪家供應商。
"""
import os
import json
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.config import settings

PROVIDERS = ["local", "anthropic", "openai", "google", "xai"]

_keys_cache = None
_keys_lock = threading.Lock()


class ProviderNotConfigured(Exception):
    """對應 provider 在 llm_keys.json 裡沒有設定 api_key。"""


def _load_keys() -> dict:
    global _keys_cache
    with _keys_lock:
        if _keys_cache is None:
            try:
                with open(settings.LLM_KEYS_PATH, encoding="utf-8") as f:
                    _keys_cache = json.load(f)
            except FileNotFoundError:
                _keys_cache = {}
        return _keys_cache


def is_configured(provider: str) -> bool:
    if provider == "local":
        return True
    if provider == "google" and os.getenv("GEMINI_API_KEY"):
        return True
    return bool(_load_keys().get(provider, {}).get("api_key"))


def key_prefix(provider: str, length: int = 4) -> str:
    """只回傳金鑰前幾碼，debug 用（例如 log 裡確認載入的是不是預期那把 key、
    有沒有多餘空白字元），不要把完整金鑰印出來或回傳給前端。"""
    key = ""
    if provider == "google":
        key = os.getenv("GEMINI_API_KEY") or ""
    if not key:
        key = _load_keys().get(provider, {}).get("api_key") or ""
    if not key:
        return "(未設定)"
    return key[:length] + "..."


def _get_config(provider: str) -> dict:
    config = dict(_load_keys().get(provider) or {})
    if provider == "google" and not config.get("api_key") and os.getenv("GEMINI_API_KEY"):
        config["api_key"] = os.getenv("GEMINI_API_KEY")
    if not config.get("api_key"):
        raise ProviderNotConfigured(
            f"尚未設定 {provider} 的 API key，請在 backend/llm_keys.json 或環境變數 GEMINI_API_KEY 填入後重啟後端。"
        )
    return config


def _split_system(messages: list[dict]):
    """回傳 (system_prompt, 其餘 messages)；Anthropic/Gemini 的 system prompt 是獨立參數，不放在 messages 陣列裡。"""
    system_prompt = ""
    rest = []
    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            rest.append(m)
    return system_prompt, rest


def generate_anthropic(messages: list[dict], max_new_tokens: int) -> str:
    import anthropic

    config = _get_config("anthropic")
    system_prompt, rest = _split_system(messages)
    client = anthropic.Anthropic(api_key=config["api_key"])
    response = client.messages.create(
        model=config.get("model", "claude-sonnet-4-5-20250929"),
        system=system_prompt,
        messages=rest,
        max_tokens=max_new_tokens,
    )
    return "".join(block.text for block in response.content if block.type == "text")


def generate_openai(messages: list[dict], max_new_tokens: int) -> str:
    from openai import OpenAI

    config = _get_config("openai")
    client = OpenAI(api_key=config["api_key"])
    response = client.chat.completions.create(
        model=config.get("model", "gpt-4o-mini"),
        messages=messages,
        max_tokens=max_new_tokens,
    )
    return response.choices[0].message.content


def generate_xai(messages: list[dict], max_new_tokens: int) -> str:
    """xAI Grok 的 API 相容 OpenAI SDK 格式，只是換一個 base_url。"""
    from openai import OpenAI

    config = _get_config("xai")
    client = OpenAI(api_key=config["api_key"], base_url="https://api.x.ai/v1")
    response = client.chat.completions.create(
        model=config.get("model", "grok-4"),
        messages=messages,
        max_tokens=max_new_tokens,
    )
    return response.choices[0].message.content


def generate_google(messages: list[dict], max_new_tokens: int) -> str:
    import google.generativeai as genai

    config = _get_config("google")
    genai.configure(api_key=config["api_key"])
    system_prompt, rest = _split_system(messages)
    model = genai.GenerativeModel(
        config.get("model", "gemini-3.1-flash-lite"),
        system_instruction=system_prompt or None,
    )

    if not rest:
        return ""

    *history, last = rest
    chat = model.start_chat(history=[
        {"role": "model" if h["role"] == "assistant" else "user", "parts": [h["content"]]}
        for h in history
    ])
    response = chat.send_message(
        last["content"],
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_new_tokens),
    )
    return response.text


def generate_local_provider(messages: list[dict], max_new_tokens: int) -> str:
    from app.llm import generate as generate_local

    return generate_local(messages, max_new_tokens=max_new_tokens)


_DISPATCH = {
    "local": generate_local_provider,
    "anthropic": generate_anthropic,
    "openai": generate_openai,
    "google": generate_google,
    "xai": generate_xai,
}


def generate_with_provider(provider: str, messages: list[dict], max_new_tokens: int = 512) -> str:
    if provider not in _DISPATCH:
        raise ValueError(f"未知的 LLM provider：{provider}")
    return _DISPATCH[provider](messages, max_new_tokens)


# ---- Tool calling（讓 LLM 自己決定要不要呼叫 MCP tool，見 app/mcp_chat.py） ----
#
# 目前只實作 Gemini（google）：實際使用的線上 provider 只有它；本地小模型（MiniCPM／Qwen 2B）
# 沒辦法可靠地選 tool，明確不支援，由呼叫端提示使用者改用其他模型。


class ToolCallingNotSupported(Exception):
    """這個 provider 目前不支援 tool calling。"""


@dataclass
class ToolCallRecord:
    """LLM 這次實際呼叫過的 tool，給對話紀錄（稽核）使用。"""
    name: str
    arguments: dict
    result: str
    is_error: bool


def supports_tool_calling(provider: str) -> bool:
    return provider == "google"


def _json_schema_to_gemini(schema: dict, defs: dict, depth: int = 0) -> dict:
    """
    把 MCP tool 的 JSON Schema 轉成 Gemini 接受的 OpenAPI 子集。
    MCP server 用 pydantic 產生的 schema 會有 $defs／$ref、anyOf（Optional）、title、default，
    Gemini SDK 會直接拒絕這些欄位；這裡展開 $ref、把 Optional 轉成 nullable、丟掉不支援的欄位。
    """
    if depth > 8:  # 遞迴保護（自我引用的 schema），太深就退成字串
        return {"type": "string"}

    if "$ref" in schema:
        target = defs.get(schema["$ref"].split("/")[-1], {})
        return _json_schema_to_gemini(target, defs, depth + 1)

    options = schema.get("anyOf") or schema.get("oneOf")
    if options:
        non_null = [o for o in options if o.get("type") != "null"]
        nullable = len(non_null) != len(options)
        if len(non_null) == 1:
            converted = _json_schema_to_gemini(non_null[0], defs, depth + 1)
        else:
            # 真正的多型別聯集 Gemini 無法表達，退成字串讓 LLM 自己以文字帶入
            converted = {"type": "string"}
        if nullable:
            converted["nullable"] = True
        if schema.get("description") and "description" not in converted:
            converted["description"] = schema["description"]
        return converted

    schema_type = schema.get("type")
    if isinstance(schema_type, list):  # ["string", "null"] 寫法
        nullable = "null" in schema_type
        schema_type = next((t for t in schema_type if t != "null"), "string")
    else:
        nullable = False
    if schema_type not in ("string", "number", "integer", "boolean", "array", "object"):
        schema_type = "object" if "properties" in schema else "string"

    out: dict[str, Any] = {"type": schema_type}
    if nullable:
        out["nullable"] = True
    if schema.get("description"):
        out["description"] = schema["description"]
    if schema_type == "string" and schema.get("enum") and all(isinstance(v, str) for v in schema["enum"]):
        out["enum"] = schema["enum"]
    if schema_type == "object":
        properties = {
            name: _json_schema_to_gemini(sub, defs, depth + 1)
            for name, sub in (schema.get("properties") or {}).items()
        }
        out["properties"] = properties
        required = [r for r in schema.get("required", []) if r in properties]
        if required:
            out["required"] = required
    if schema_type == "array":
        out["items"] = _json_schema_to_gemini(schema.get("items") or {"type": "string"}, defs, depth + 1)
    return out


def _to_gemini_function_declaration(tool) -> dict:
    declaration: dict[str, Any] = {"name": tool.name, "description": tool.description or tool.name}
    parameters = _json_schema_to_gemini(tool.input_schema or {}, (tool.input_schema or {}).get("$defs", {}))
    # 沒有參數的 tool：Gemini 不接受「properties 為空的 object」，必須整個省略 parameters
    if parameters.get("properties"):
        declaration["parameters"] = parameters
    return declaration


ToolCaller = Callable[[str, dict], Awaitable[Any]]  # (tool 名稱, 參數) -> McpToolResult


def _gemini_function_calls(response) -> list:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return []
    return [p.function_call for p in candidates[0].content.parts if p.function_call and p.function_call.name]


def _gemini_text(response) -> str:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return ""
    return "".join(p.text for p in candidates[0].content.parts if p.text)


async def _run_gemini_tool_loop(
    chat, message: str, tools: list, call_tool: ToolCaller, max_new_tokens: int, max_rounds: int,
) -> tuple[str, list[ToolCallRecord]]:
    """
    Gemini 的 tool 迴圈：送出問題 → 若模型要呼叫 tool 就執行並把結果送回 → 重複，直到模型直接給出文字答案。
    最多 max_rounds 輪；最後一輪把 function calling 關掉（mode NONE），強迫它用手上的資訊回答，
    避免無限迴圈。chat 是 Gemini 的 ChatSession（測試時可換成假物件）。
    """
    import google.generativeai as genai

    known_tools = {t.name for t in tools}
    records: list[ToolCallRecord] = []
    generation_config = genai.types.GenerationConfig(max_output_tokens=max_new_tokens)

    response = await chat.send_message_async(message, generation_config=generation_config)
    for round_number in range(1, max_rounds + 1):
        calls = _gemini_function_calls(response)
        if not calls:
            break

        response_parts = []
        for call in calls:
            arguments = genai.protos.FunctionCall.to_dict(call).get("args") or {}
            if call.name not in known_tools:
                # 模型編造了不存在的 tool 名稱：不送去 server，直接回報錯誤讓它改用其他方式回答
                result_text, is_error = f"沒有名為 {call.name} 的工具。", True
            else:
                result = await call_tool(call.name, arguments)
                result_text, is_error = result.text, result.is_error
            records.append(ToolCallRecord(call.name, arguments, result_text, is_error))
            payload = {"error": result_text} if is_error else {"result": result_text}
            response_parts.append(
                genai.protos.Part(function_response=genai.protos.FunctionResponse(name=call.name, response=payload))
            )

        kwargs: dict[str, Any] = {"generation_config": generation_config}
        if round_number == max_rounds:
            kwargs["tool_config"] = {"function_calling_config": {"mode": "NONE"}}
        response = await chat.send_message_async(response_parts, **kwargs)

    return _gemini_text(response), records


async def generate_with_tools(
    provider: str, messages: list[dict], tools: list, call_tool: ToolCaller,
    max_new_tokens: int = 2048, max_rounds: int | None = None,
) -> tuple[str, list[ToolCallRecord]]:
    """
    讓 LLM 使用 tools（app.mcp_client.McpTool 清單）回答，回傳（最終文字答案, 實際呼叫過的 tool 紀錄）。
    messages 格式同 generate_with_provider()；最後一則必須是使用者的問題。
    """
    if not supports_tool_calling(provider):
        raise ToolCallingNotSupported(f"{provider} 不支援 tool calling")

    import google.generativeai as genai

    config = _get_config("google")
    genai.configure(api_key=config["api_key"])
    system_prompt, rest = _split_system(messages)
    if not rest:
        return "", []
    model = genai.GenerativeModel(
        config.get("model", "gemini-3.1-flash-lite"),
        system_instruction=system_prompt or None,
        tools=[{"function_declarations": [_to_gemini_function_declaration(t) for t in tools]}] if tools else None,
    )
    *history, last = rest
    chat = model.start_chat(history=[
        {"role": "model" if h["role"] == "assistant" else "user", "parts": [h["content"]]}
        for h in history
    ])
    return await _run_gemini_tool_loop(
        chat, last["content"], tools, call_tool, max_new_tokens, max_rounds or settings.MCP_MAX_TOOL_ROUNDS
    )
