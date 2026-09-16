import type { CompanyInfo } from "./auth";

const API_BASE_URL = import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function listCompanies(token: string): Promise<CompanyInfo[]> {
  const response = await fetch(`${API_BASE_URL}/api/admin/companies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
  const data = (await response.json()) as { companies: CompanyInfo[] };
  return data.companies;
}

export async function createCompany(
  token: string,
  params: { name: string; mcp_url?: string; welcome_message?: string; quick_replies?: string[] }
): Promise<CompanyInfo> {
  const response = await fetch(`${API_BASE_URL}/api/admin/companies`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(params),
  });
  await throwIfNotOk(response);
  return (await response.json()) as CompanyInfo;
}

export async function deleteCompany(token: string, companyId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/admin/companies/${encodeURIComponent(companyId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  await throwIfNotOk(response);
}

export async function updateCompany(
  token: string,
  companyId: string,
  params: { name?: string; mcp_url?: string; welcome_message?: string; quick_replies?: string[] }
): Promise<CompanyInfo> {
  const response = await fetch(`${API_BASE_URL}/api/admin/companies/${encodeURIComponent(companyId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(params),
  });
  await throwIfNotOk(response);
  return (await response.json()) as CompanyInfo;
}
