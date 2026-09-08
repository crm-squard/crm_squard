"""
當日提問摘要：給管理者看「今天使用者都在問什麼」的功能。

流程：
1. 從 chat_log 撈出指定日期的所有提問原文
2. 問題數量較多時先分批（每批 SUMMARY_BATCH_SIZE 則）各自摘要成主題重點，
   避免一次把所有問題塞進 LLM context（本地小模型 context 有限，問題一多會爆或品質變差）
3. 有多批的話，再把每批摘要匯總、做一次「摘要的摘要」，產生最終報告

這是 map-reduce 的簡化版本，資料量大時可以再拆更細；目前先滿足小型客服場景。

LLM 選擇：優先用有設定金鑰的線上 provider（依 _SUMMARY_PROVIDER_PRIORITY 順序），
都沒有設定才 fallback 用本地模型。這樣線上環境（例如只裝了線上 API 依賴、沒裝 torch 的部署）
只要設定好任一組線上金鑰，就不會走到本地模型、也不會因為 torch 沒裝而出錯。
"""
from app.chat_log import get_messages_for_date
from app.providers import generate_with_provider, is_configured

SUMMARY_BATCH_SIZE = 30
_SUMMARY_PROVIDER_PRIORITY = ["google", "anthropic", "openai", "xai"]

_BATCH_SYSTEM_PROMPT = (
    "你是客服數據分析助理，負責幫管理者整理顧客提問紀錄。"
    "請閱讀以下顧客提問清單，歸納出幾個常見主題與重點，用條列式呈現，"
    "並標註每個主題大約出現幾次。不要逐條複述原始問題，只保留有意義的歸納。"
)

_REDUCE_SYSTEM_PROMPT = (
    "你是客服數據分析助理。以下是同一天內、分批整理出來的多份主題摘要，"
    "請把它們合併成一份最終摘要：相同或相似的主題要合併並加總次數，"
    "用條列式呈現最終結果，並在最後加一行「總結」簡短說明今天顧客最關心的重點。"
)


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _pick_provider() -> str:
    for provider in _SUMMARY_PROVIDER_PRIORITY:
        if is_configured(provider):
            return provider
    return "local"


# 拉高到 1500（原本 400）：fallback 用的本地小模型 openbmb/MiniCPM5-2B 預設用
# enable_thinking=False 關掉思考過程，正常用不到這麼多，拉高只是留安全餘裕
# （見 app/agent.py 的 generate_answer() 同樣理由）。
_SUMMARY_MAX_NEW_TOKENS = 1500


def _summarize_batch(questions: list[str], provider: str) -> str:
    question_list = "\n".join(f"- {q}" for q in questions)
    messages = [
        {"role": "system", "content": _BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": f"顧客提問清單：\n{question_list}"},
    ]
    return generate_with_provider(provider, messages, max_new_tokens=_SUMMARY_MAX_NEW_TOKENS)


def _reduce_summaries(batch_summaries: list[str], provider: str) -> str:
    combined = "\n\n".join(f"[第 {i+1} 批摘要]\n{s}" for i, s in enumerate(batch_summaries))
    messages = [
        {"role": "system", "content": _REDUCE_SYSTEM_PROMPT},
        {"role": "user", "content": combined},
    ]
    return generate_with_provider(provider, messages, max_new_tokens=_SUMMARY_MAX_NEW_TOKENS)


def summarize_day(date: str) -> dict:
    """date 格式為 YYYY-MM-DD（UTC）。回傳當天提問數量與摘要文字。"""
    questions = get_messages_for_date(date)
    if not questions:
        return {"date": date, "question_count": 0, "summary": "當天沒有使用者提問紀錄。"}

    provider = _pick_provider()
    batches = _chunk(questions, SUMMARY_BATCH_SIZE)
    batch_summaries = [_summarize_batch(b, provider) for b in batches]

    summary = batch_summaries[0] if len(batch_summaries) == 1 else _reduce_summaries(batch_summaries, provider)

    return {"date": date, "question_count": len(questions), "summary": summary}
