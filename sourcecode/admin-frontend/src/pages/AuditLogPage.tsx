import Card from "antd/es/card";
import List from "antd/es/list";
import message from "antd/es/message";
import Typography from "antd/es/typography";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { listAuditLog, type AuditLogEntry } from "../api/auditLog";
import { useAuth } from "../auth/AuthContext";
import AdminPageLayout from "../components/AdminPageLayout";
import ChatbotSettingsTabs from "../components/ChatbotSettingsTabs";
import { ui } from "../uiStyles";

const { Paragraph } = Typography;

const ACTION_LABELS: Record<string, string> = {
  create_chatbot: "建立商家服務",
  update_chatbot: "更新商家設定",
  reveal_mcp_token: "查看 MCP 金鑰",
  delete_chatbot: "刪除商家服務",
  create_account: "新增帳號",
  delete_account: "移除帳號",
  self_register: "帳號自助註冊",
  upsert_document: "上傳/更新知識庫文件",
  delete_document: "刪除知識庫文件",
};

export default function AuditLogPage() {
  const { token, selectedChatbotId } = useAuth();
  const [messageApi, contextHolder] = message.useMessage();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token || !selectedChatbotId) return;

    let isCurrent = true;
    setLoading(true);
    listAuditLog(token, selectedChatbotId)
      .then((result) => {
        if (isCurrent) setEntries(result);
      })
      .catch((error) => {
        if (!isCurrent) return;
        messageApi.error(
          error instanceof Error ? error.message : "稽核紀錄載入失敗",
        );
      })
      .finally(() => {
        if (isCurrent) setLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [messageApi, selectedChatbotId, token]);

  if (!token) return <Navigate to="/login" replace />;
  if (!selectedChatbotId) return <Navigate to="/chatbots" replace />;

  return (
    <AdminPageLayout
      title="稽核紀錄"
      description="查看目前 ChatBot 設定與資源的異動紀錄。"
      beforeHeader={contextHolder}
    >
      <ChatbotSettingsTabs />
      <Card className={ui.settingsCard} title="稽核紀錄">
        <Paragraph type="secondary">
          這家商家服務最近的異動紀錄：建立或刪除、設定變更、知識庫文件及協作帳號異動。
        </Paragraph>
        <List
          dataSource={entries}
          loading={loading}
          locale={{ emptyText: "目前沒有紀錄。" }}
          renderItem={(entry) => (
            <List.Item>
              <List.Item.Meta
                title={ACTION_LABELS[entry.action] ?? entry.action}
                description={`${entry.actor_email ?? "未知帳號"} · ${entry.created_at ?? ""}`}
              />
            </List.Item>
          )}
        />
      </Card>
    </AdminPageLayout>
  );
}
