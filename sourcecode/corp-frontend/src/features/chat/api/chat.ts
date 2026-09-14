import type { ChatRequest, ChatResponse, ProviderInfo } from "../../../types/api";
import { parseChatResponse, parseProviders } from "./validation";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function askBackend(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
  const data: unknown = await response.json();
  return parseChatResponse(data);
}

export async function fetchProviders(): Promise<ProviderInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/providers`);
  if (!response.ok) throw new Error(`後端回應錯誤：${response.status}`);
  const data: unknown = await response.json();
  return parseProviders(data);
}
