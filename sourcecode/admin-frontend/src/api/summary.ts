export interface QuestionCategory {
  name: string;
  count: number;
}

export interface DailySummary {
  date: string;
  question_count: number;
  categories: QuestionCategory[];
  meaningless_questions: string[];
  needs_merchant_attention: string[];
  summary: string;
}

const API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function getDailySummary(
  token: string,
  chatbotId: string,
  date?: string,
): Promise<DailySummary> {
  const url = new URL(`${API_BASE_URL}/api/admin/summary`);
  url.searchParams.set("chatbot_id", chatbotId);
  if (date) url.searchParams.set("date", date);
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
  return (await response.json()) as DailySummary;
}
