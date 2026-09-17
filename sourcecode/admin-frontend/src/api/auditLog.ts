const API_BASE_URL =
  import.meta.env.VITE_RAG_API_URL || "http://localhost:8000";

export interface AuditLogEntry {
  id: number;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  detail: unknown;
  created_at: string | null;
}

async function throwIfNotOk(response: Response): Promise<void> {
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`後端回應狀態碼 ${response.status}: ${body}`);
  }
}

export async function listAuditLog(
  token: string,
  chatbotId: string,
): Promise<AuditLogEntry[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/admin/audit-log?chatbot_id=${encodeURIComponent(chatbotId)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  await throwIfNotOk(response);
  const data = (await response.json()) as { entries: AuditLogEntry[] };
  return data.entries;
}
