import type { Account, AccountRole } from "./auth";

const API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

// 帶 companyId：查這家公司綁定的商家帳號（公司設定頁「管理帳號」用，不含管理者帳號）。
// 不帶：查全部管理者帳號（「管理者帳號」頁籤用，僅限 platform 角色）。
export async function listAccounts(
  token: string,
  companyId?: string,
): Promise<Account[]> {
  const url = companyId
    ? `${API_BASE_URL}/api/admin/accounts?company_id=${encodeURIComponent(companyId)}`
    : `${API_BASE_URL}/api/admin/accounts`;
  const response = await fetch(url, {
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
