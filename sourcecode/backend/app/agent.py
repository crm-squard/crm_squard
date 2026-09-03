"""
ProductQueryAgent：對應「智慧CRM系統功能提案 #1 顧客查詢產品資訊」流程 01~04。

- receive_query()    -> 01 使用者跟機器人查詢產品內容
- vectorize_query()  -> 02 Agent 將 input 向量化
- retrieve_from_kb() -> 03 查詢 RAG 資料庫
- generate_answer()  -> 04 根據 RAG 查詢結果給 LLM 回答（整合 01~03 的完整流程入口）
"""
from app.rag.vectorstore import get_collection
from app.rag.embedding import embed_query
from app.llm import get_llm, generate as llm_generate

SYSTEM_PROMPT = (
    "你是客服機器人，請根據提供的產品資訊片段回答顧客問題，不可使用片段以外的知識自行編造內容。"
    "回答時請在句子後方以（產品：產品名稱）的格式標註是哪個產品的資訊。"
)

NO_INFO_ANSWER = "目前查無此資訊，建議聯繫真人客服（0800-123-456）。"

# 檢索距離超過這個門檻就直接回「查無此資訊」，不呼叫 LLM。
#
# 原本是讓 LLM 自己判斷「片段裡有沒有答案」，但實測發現 1.5B 這種小模型在這個判斷上非常不穩定：
# system prompt 只要多加幾條規則、或換幾個字，同一個問題就會在「查無資訊」跟「正確回答」之間跳來跳去
# （例如把「如果片段」改成「如果產品資訊片段」這種無關痛癢的用字差異，就能讓模型從答對變成拒答）。
# 既然檢索距離分數本身很穩定準確（實測相關片段都在 0.22~0.28，不相關的都在 0.33 以上），
# 乾脆用距離分數做這個判斷，不要交給小模型猜。
#
# 這個門檻是用目前 20 項產品的測試資料手動抓出來的經驗值，不是嚴謹算出來的，
# 之後資料量變大或換 embedding 模型，應該要重新用實際問題校準這個數字。
NO_INFO_DISTANCE_THRESHOLD = 0.30


class ProductQueryAgent:
    def __init__(self, system_prompt: str = SYSTEM_PROMPT):
        self.collection = get_collection()
        get_llm()  # 建構時就把 LLM 一併載入，讓 get_agent() 真正做到完整預載
        self.system_prompt = system_prompt

    def receive_query(self, query: str) -> str:
        return query.strip()

    def vectorize_query(self, query: str):
        return embed_query(query)

    def retrieve_from_kb(self, query_embedding, top_k: int = 3):
        results = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        retrieved = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            retrieved.append({
                "text": doc,
                "source": meta["source"],
                "product_name": meta.get("product_name", ""),
                "category": meta.get("category", ""),
                "distance": dist,
            })
        return retrieved

    def _build_retrieval_query(self, query: str, history) -> str:
        if not history:
            return query
        last_user_turn = next(
            (h["content"] for h in reversed(history) if h.get("role") == "user"),
            None,
        )
        if not last_user_turn:
            return query
        return f"{last_user_turn} {query}"

    def _build_prompt(self, query: str, retrieved_chunks) -> str:
        context_text = "\n\n".join(
            f"[片段 {i+1}，產品：{r['product_name']}]\n{r['text']}"
            for i, r in enumerate(retrieved_chunks)
        )
        return (
            f"產品資訊片段：\n{context_text}\n\n"
            f"顧客問題：{query}\n\n"
            f"請根據以上產品資訊片段回答顧客問題。"
        )

    def generate_answer(self, query: str, history=None, top_k: int = 3, max_new_tokens: int = 512):
        """
        history：之前幾輪對話 [{"role": "user"|"assistant", "content": ...}, ...]，
        用來讓機器人理解「那電池呢？」這種依賴上文的追問。

        「那電池呢？」這句話本身沒有主詞，單獨拿去向量化檢索會查到不相關的片段
        （例如查成電視遙控器電池而不是掃地機器人電池）。所以檢索用的查詢字串會把
        上一輪使用者的問題也接進來，補上缺的主詞；但送給 LLM 的「顧客問題」欄位
        仍用原始這句話，回答語氣才自然。
        """
        clean_query = self.receive_query(query)
        retrieval_query = self._build_retrieval_query(clean_query, history)
        query_embedding = self.vectorize_query(retrieval_query)
        retrieved_chunks = self.retrieve_from_kb(query_embedding, top_k=top_k)

        if not retrieved_chunks or retrieved_chunks[0]["distance"] > NO_INFO_DISTANCE_THRESHOLD:
            return NO_INFO_ANSWER, []

        user_prompt = self._build_prompt(clean_query, retrieved_chunks)

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user_prompt})
        answer = llm_generate(messages, max_new_tokens=max_new_tokens)

        return answer, retrieved_chunks


_agent: ProductQueryAgent | None = None


def get_agent() -> ProductQueryAgent:
    global _agent
    if _agent is None:
        _agent = ProductQueryAgent()
    return _agent
