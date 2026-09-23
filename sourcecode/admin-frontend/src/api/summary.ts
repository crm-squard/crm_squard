import { requestAdminApi } from "./apiClient";

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

export async function getDailySummary(
  token: string,
  chatbotId: string,
  date?: string,
): Promise<DailySummary> {
  const searchParams = new URLSearchParams({ chatbot_id: chatbotId });
  if (date) searchParams.set("date", date);
  return requestAdminApi<DailySummary>(
    `/api/admin/summary?${searchParams.toString()}`,
    { token },
  );
}
