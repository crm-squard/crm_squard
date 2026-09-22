import Space from "antd/es/space";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { ui } from "../uiStyles";
import { tw } from "../utils/tw";

interface AdminPageLayoutProps {
  title: ReactNode;
  description: ReactNode;
  headerExtra?: ReactNode;
  headerLeading?: ReactNode;
  beforeHeader?: ReactNode;
  variant?: "default" | "detail";
  children: ReactNode;
}

export default function AdminPageLayout({
  title,
  description,
  headerExtra,
  headerLeading,
  beforeHeader,
  variant = "default",
  children,
}: AdminPageLayoutProps) {
  const { chatbots, selectedChatbotId } = useAuth();
  const selectedChatbotName = chatbots.find(
    (chatbot) => chatbot.id === selectedChatbotId,
  )?.name;

  return (
    <main className={ui.pageContent}>
      {beforeHeader}
      <div className={ui.pageHeaderGroup}>
        <div
          className={tw(
            ui.pageHeading,
            variant === "detail" && ui.detailHeading,
          )}
        >
          <div>
            {headerLeading}
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          {headerExtra}
        </div>
        {selectedChatbotName ? (
          <strong className={ui.currentChatbotName}>
            目前商家：{selectedChatbotName}
          </strong>
        ) : null}
      </div>

      <Space className={ui.fullWidth} direction="vertical" size={16}>
        {children}
      </Space>
    </main>
  );
}
