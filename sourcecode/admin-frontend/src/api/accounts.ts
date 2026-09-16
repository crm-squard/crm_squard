import type { Account, AccountRole } from "./auth";

const API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function listAccounts(token: string): Promise<Account[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/accounts`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
  const data = (await response.json()) as { accounts: Account[] };
  return data.accounts;
}

export async function createAccount(
  token: string,
  params: { email: string; role: AccountRole; company_id?: string },
): Promise<Account> {
  const response = await fetch(`${API_BASE_URL}/api/admin/accounts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(params),
  });
  await throwIfNotOk(response);
  return (await response.json()) as Account;
}

export async function deleteAccount(
  token: string,
  accountId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/accounts/${encodeURIComponent(accountId)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  await throwIfNotOk(response);
}
