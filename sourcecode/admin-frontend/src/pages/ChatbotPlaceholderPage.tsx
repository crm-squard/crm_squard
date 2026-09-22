import Card from "antd/es/card";
import Typography from "antd/es/typography";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import ChatbotSettingsTabs from "../components/ChatbotSettingsTabs";
import CopyableIdentifier from "../components/CopyableIdentifier";
import AdminPageLayout from "../components/AdminPageLayout";
import { ui } from "../uiStyles";

const pageContent: Record<string, { title: string; description: string }> = {
  "/chatbots/linebot-settings": {
    title: "LineBot 設定",
    description: "設定 ChatBot 與 LINE 官方帳號的連線方式。",
  },
  "/chatbots/script-settings": {
    title: "腳本設定",
    description: "程式碼嵌入商家網站，讓網站載入目前商家的聊天機器人。",
  },
};

const { Paragraph, Text } = Typography;

export default function ChatbotPlaceholderPage() {
  const location = useLocation();
  const { selectedChatbotId, chatbots } = useAuth();
  const content = pageContent[location.pathname];

  if (!selectedChatbotId) return <Navigate to="/chatbots" replace />;
  if (!content) return <Navigate to="/chatbots" replace />;

  const chatbot = chatbots.find((item) => item.id === selectedChatbotId);
  const adminFrontendUrl = (
    import.meta.env.VITE_ADMIN_FRONTEND_URL || "http://localhost:5174/"
  ).replace(/\/$/, "");
  const embedScript = chatbot
    ? `<script src="${adminFrontendUrl}/chat-widget.js" data-client-id="${chatbot.id}"></script>`
    : "";

  return (
    <AdminPageLayout title={content.title} description={content.description}>
      <ChatbotSettingsTabs />
      <Card className={ui.settingsCard} title="嵌入程式碼">
        {location.pathname === "/chatbots/script-settings" && chatbot ? (
          <>
            <div className="pb-10">
              <CopyableIdentifier label="複製嵌入程式碼" value={embedScript} />
            </div>
            <Paragraph>
              請將上面程式碼貼到網站的 <Text code>&lt;html&gt;</Text> 標籤內。
            </Paragraph>
            <pre className="mb-4 overflow-x-auto rounded-lg bg-slate-950 p-4 text-sm text-slate-100">
              <code>{`<html>\n  ...\n  ${embedScript}\n</html>`}</code>
            </pre>
          </>
        ) : (
          <div className={ui.settingsPlaceholder}>
            此功能目前尚未支援，待 API 完成後開放。
          </div>
        )}
      </Card>
    </AdminPageLayout>
  );
}
