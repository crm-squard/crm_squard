import type { ChatbotInfo } from "./auth";

const API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function listChatbots(token: string): Promise<ChatbotInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/chatbots`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
  const data = (await response.json()) as { chatbots: ChatbotInfo[] };
  return data.chatbots;
}

export async function createChatbot(
  token: string,
  params: {
    name: string;
    mcp_url?: string;
    welcome_message?: string;
    quick_replies?: string[];
  },
): Promise<ChatbotInfo> {
  const response = await fetch(`${API_BASE_URL}/api/admin/chatbots`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(params),
  });
  await throwIfNotOk(response);
  return (await response.json()) as ChatbotInfo;
}

export async function deleteChatbot(
  token: string,
  chatbotId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/chatbots/${encodeURIComponent(chatbotId)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  await throwIfNotOk(response);
}

export async function updateChatbot(
  token: string,
  chatbotId: string,
  params: {
    name?: string;
    mcp_url?: string;
    welcome_message?: string;
    quick_replies?: string[];
  },
): Promise<ChatbotInfo> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/chatbots/${encodeURIComponent(chatbotId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(params),
    },
  );
  await throwIfNotOk(response);
  return (await response.json()) as ChatbotInfo;
}
