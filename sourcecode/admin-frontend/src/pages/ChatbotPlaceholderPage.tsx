import Card from "antd/es/card";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import ChatbotSettingsTabs from "../components/ChatbotSettingsTabs";
import AdminPageLayout from "../components/AdminPageLayout";
import { ui } from "../uiStyles";

const pageContent: Record<string, { title: string; description: string }> = {
  "/chatbots/linebot-settings": {
    title: "LineBot 設定",
    description: "設定 ChatBot 與 LINE 官方帳號的連線方式。",
  },
  "/chatbots/script-settings": {
    title: "腳本設定",
    description: "管理 ChatBot 可使用的機器人腳本。",
  },
};

export default function ChatbotPlaceholderPage() {
  const location = useLocation();
  const { selectedChatbotId } = useAuth();
  const content = pageContent[location.pathname];

  if (!selectedChatbotId) return <Navigate to="/chatbots" replace />;
  if (!content) return <Navigate to="/chatbots" replace />;

  return (
    <AdminPageLayout title={content.title} description={content.description}>
      <ChatbotSettingsTabs />
      <Card className={ui.settingsCard}>
        <div className={ui.settingsPlaceholder}>
          此功能目前尚未支援，待 API 完成後開放。
        </div>
      </Card>
    </AdminPageLayout>
  );
}
