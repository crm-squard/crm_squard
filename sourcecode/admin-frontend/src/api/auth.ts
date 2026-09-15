export type AccountRole = "platform_primary" | "platform_secondary" | "tenant_primary" | "tenant_secondary";

export interface Account {
  id: string;
  email: string;
  role: AccountRole;
  created_by: string | null;
  created_at: string;
}

export interface CompanyInfo {
  id: string;
  name: string;
  mcp_url: string | null;
  welcome_message: string | null;
  quick_replies: string[] | null;
  created_at: string;
}

export interface MeResponse {
  account: Account;
  companies: CompanyInfo[];
}

export interface LoginResponse {
  token: string;
  account: Account;
}

// 跟 documents.ts 打同一個 backend 服務（8000 埠），沿用同一組 base URL 慣例。
const API_BASE_URL = import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function loginWithGoogle(idToken: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  await throwIfNotOk(response);
  return (await response.json()) as LoginResponse;
}

export async function logout(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
}

export async function getMe(token: string): Promise<MeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
  return (await response.json()) as MeResponse;
}
