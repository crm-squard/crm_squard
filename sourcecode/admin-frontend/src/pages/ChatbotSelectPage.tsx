import Button from "antd/es/button";
import Card from "antd/es/card";
import Form from "antd/es/form";
import Input from "antd/es/input";
import List from "antd/es/list";
import message from "antd/es/message";
import Tag from "antd/es/tag";
import Typography from "antd/es/typography";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import BrandMark from "../components/BrandMark";
import { ui } from "../uiStyles";
import { useAuth } from "../auth/AuthContext";
import { createChatbot } from "../api/chatbots";
import type { ChatbotInfo } from "../api/auth";

const { Text } = Typography;

export default function ChatbotSelectPage() {
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const { token, chatbots, selectedChatbotId, selectChatbot, refreshMe } =
    useAuth();
  const [creating, setCreating] = useState(false);
  const [chatbotList, setChatbotList] = useState<ChatbotInfo[]>(chatbots);
  const [form] = Form.useForm<{ name: string }>();

  useEffect(() => {
    setChatbotList(chatbots);
  }, [chatbots]);

  // 只有一家公司、且「還沒選過」（剛登入、第一次進來）時，自動選定並跳過此頁——
  // 條件限定在 !selectedChatbotId，所以之後從 AdminLayout 的「管理商家服務」手動回到
  // 這一頁時（此時 selectedChatbotId 已經有值）不會被這個 effect 搶著導走，頁面才能
  // 真的用來新增/切換第二家以後的商家（不然選過一次之後就永遠回不到這頁了）。
  useEffect(() => {
    if (chatbotList.length === 1 && !selectedChatbotId) {
      selectChatbot(chatbotList[0].id);
      navigate("/", { replace: true });
    }
  }, [chatbotList, selectedChatbotId, selectChatbot, navigate]);

  if (!token) return <Navigate to="/login" replace />;

  async function handleCreate(values: { name: string }) {
    if (!token) return;
    setCreating(true);
    try {
      await createChatbot(token, { name: values.name });
      await refreshMe();
      form.resetFields();
      messageApi.success(
        "已新增商家服務，MCP URL／開頭語可以到「Chatbot 設定」頁面填寫",
      );
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "新增失敗");
    } finally {
      setCreating(false);
    }
  }

  async function handleCopyId(chatbotId: string) {
    try {
      await navigator.clipboard.writeText(chatbotId);
      messageApi.success("已複製商家識別碼");
    } catch {
      messageApi.error("複製失敗，請手動選取文字複製。");
    }
  }

  function goToSettings(chatbotId: string) {
    selectChatbot(chatbotId);
    navigate("/chatbot-settings");
  }

  return (
    <main className={ui.centeredPage}>
      {contextHolder}
      <div className={ui.chatbotSelectCard}>
        <BrandMark />
        <h1>選擇要管理的商家</h1>
        {chatbotList.length === 0 ? (
          <Text type="secondary">目前沒有可管理的商家，請聯繫平台管理員。</Text>
        ) : (
          <List
            dataSource={chatbotList}
            renderItem={(chatbot) => {
              // chatbotList 本來就是「這個帳號看得到的公司」（platform 看全部、tenant 看自己
              // 綁定的），能看到就代表 update_chatbot 的權限檢查（require_chatbot_access）
              // 也會過，所以不用再依角色隱藏「設定」按鈕。
              return (
                <List.Item
                  actions={[
                    <Button
                      key="settings"
                      onClick={() => goToSettings(chatbot.id)}
                    >
                      設定
                    </Button>,
                    <Button
                      key="select"
                      type="primary"
                      onClick={() => {
                        selectChatbot(chatbot.id);
                        navigate("/", { replace: true });
                      }}
                    >
                      選擇
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <>
                        {chatbot.name}
                        {chatbot.your_role ? (
                          <Tag
                            className="ml-2"
                            color={chatbot.your_role === "primary" ? "blue" : "default"}
                          >
                            {chatbot.your_role === "primary" ? "主帳號" : "協作帳號"}
                          </Tag>
                        ) : null}
                      </>
                    }
                    description={
                      <Text
                        type="secondary"
                        code
                        copyable={{
                          text: chatbot.id,
                          onCopy: () => handleCopyId(chatbot.id),
                        }}
                      >
                        商家識別碼：{chatbot.id}
                      </Text>
                    }
                  />
                </List.Item>
              );
            }}
          />
        )}

        <Card size="small" title="新增商家服務" className="mt-2">
          <Form form={form} layout="inline" onFinish={handleCreate}>
            <Form.Item
              name="name"
              rules={[{ required: true, message: "請輸入商家名稱" }]}
            >
              <Input placeholder="商家名稱" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={creating}>
                新增
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </main>
  );
}
