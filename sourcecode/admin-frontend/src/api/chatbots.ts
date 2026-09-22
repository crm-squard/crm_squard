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
    mcp_token?: string;
    mcp_trigger_name?: string;
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
    // 不帶＝不變更；空字串＝清除金鑰
    mcp_token?: string;
    // 不帶＝不變更；空字串＝回到預設的 MCP
    mcp_trigger_name?: string;
    welcome_message?: string;
    quick_replies?: string[];
    // 送給 LLM 的片段數（1～10）；不帶＝不變更
    rag_top_k?: number;
    // true 只在伺服器支援時才能設（否則後端回 400）；不帶＝不變更
    rerank_enabled?: boolean;
    // LINE Messaging API 設定；Channel ID 僅供記錄。
    line_channel_id?: string;
    line_channel_secret?: string;
    line_channel_access_token?: string;
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

/** 查看這家公司的 MCP 金鑰明文；每次查看後端都會寫入稽核紀錄。 */
export async function getChatbotMcpToken(
  token: string,
  chatbotId: string,
): Promise<string | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/chatbots/${encodeURIComponent(chatbotId)}/mcp-token`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  await throwIfNotOk(response);
  const data = (await response.json()) as { mcp_token: string | null };
  return data.mcp_token;
}
