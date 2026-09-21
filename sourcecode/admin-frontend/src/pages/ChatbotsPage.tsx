import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import MoreOutlined from "@ant-design/icons/MoreOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import SettingOutlined from "@ant-design/icons/SettingOutlined";
import Button from "antd/es/button";
import Card from "antd/es/card";
import Dropdown from "antd/es/dropdown";
import Empty from "antd/es/empty";
import Form from "antd/es/form";
import Input from "antd/es/input";
import message from "antd/es/message";
import Modal from "antd/es/modal";
import Spin from "antd/es/spin";
import Typography from "antd/es/typography";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { deleteChatbot, createChatbot } from "../api/chatbots";
import { useAuth } from "../auth/AuthContext";
import AdminPageLayout from "../components/AdminPageLayout";
import { ui } from "../uiStyles";

const { Text } = Typography;

function formatLastEditedAt(value: string | null): string {
  // API 尚未提供 updated_at，先以 created_at 作為設計稿欄位的示意資料。
  if (!value) return "--";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("zh-TW", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getInitial(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || "C";
}

export default function ChatbotsPage() {
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const { token, chatbots, selectedChatbotId, selectChatbot, refreshMe } =
    useAuth();
  const [form] = Form.useForm<{ name: string }>();
  const [isRefreshing, setIsRefreshing] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!token) return;

    let isCurrent = true;
    void refreshMe()
      .catch((err) => {
        if (!isCurrent) return;
        messageApi.error(
          err instanceof Error ? err.message : "ChatBot 列表載入失敗",
        );
      })
      .finally(() => {
        if (isCurrent) setIsRefreshing(false);
      });

    return () => {
      isCurrent = false;
    };
    // refreshMe 會因 AuthContext state 更新而變更參照；列表只需在進入頁面時重新整理一次。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!token) return <Navigate to="/login" replace />;
  const authToken = token;

  function goToSettings(chatbotId: string) {
    selectChatbot(chatbotId);
    navigate("/chatbot-settings");
  }

  function openCreateModal() {
    form.resetFields();
    setCreateOpen(true);
  }

  async function handleCreate() {
    let values: { name: string };

    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    setCreating(true);
    try {
      await createChatbot(authToken, { name: values.name.trim() });
      await refreshMe();
      setCreateOpen(false);
      messageApi.success("已新增 ChatBot");
    } catch (err) {
      messageApi.error(
        err instanceof Error ? err.message : "新增 ChatBot 失敗",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete() {
    if (!pendingDeleteId) return;

    setDeleting(true);
    try {
      await deleteChatbot(authToken, pendingDeleteId);
      if (selectedChatbotId === pendingDeleteId) selectChatbot(null);
      await refreshMe();
      setPendingDeleteId(null);
      messageApi.success("已刪除 ChatBot");
    } catch (err) {
      messageApi.error(
        err instanceof Error ? err.message : "刪除 ChatBot 失敗",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AdminPageLayout
      title="ChatBot"
      description="建立並設定商家的 AI Agent，管理角色、模型、知識庫與自動化工具。"
      beforeHeader={contextHolder}
    >
        <div className={ui.chatbotsCardHeader}>
          <h2>ChatBot 列表</h2>
          <Button
            className={ui.chatbotsCreateButton}
            icon={<PlusOutlined />}
            type="primary"
            onClick={openCreateModal}
          >
            新增 ChatBot
          </Button>
        </div>

        {isRefreshing ? (
          <div className={ui.routeLoading} role="status">
            <Spin size="small" />
            <span>載入 ChatBot 列表…</span>
          </div>
        ) : chatbots.length === 0 ? (
          <Empty className="my-10" description="目前沒有可管理的 ChatBot">
            <Button
              icon={<PlusOutlined />}
              type="primary"
              onClick={openCreateModal}
            >
              新增第一個 ChatBot
            </Button>
          </Empty>
        ) : (
          <section aria-labelledby="published-chatbots-heading">
            <div className={ui.chatbotsGrid}>
              {chatbots.map((chatbot) => (
                <article className={ui.chatbotCard} key={chatbot.id}>
                  <div className={ui.chatbotCardTitle}>
                    <div aria-hidden="true" className={ui.chatbotAvatar}>
                      {getInitial(chatbot.name)}
                    </div>
                    <h3>
                      <button
                        aria-label={`設定 ${chatbot.name}`}
                        className={ui.chatbotTitleButton}
                        title={chatbot.name}
                        type="button"
                        onClick={() => goToSettings(chatbot.id)}
                      >
                        {chatbot.name}
                      </button>
                    </h3>
                    <Dropdown
                      menu={{
                        items: [
                          {
                            key: "settings",
                            icon: <SettingOutlined />,
                            label: "前往設定",
                          },
                          {
                            danger: true,
                            key: "delete",
                            icon: <DeleteOutlined />,
                            label: "刪除 ChatBot",
                          },
                        ],
                        onClick: ({ key }) => {
                          if (key === "settings") goToSettings(chatbot.id);
                          if (key === "delete") setPendingDeleteId(chatbot.id);
                        },
                      }}
                      trigger={["click"]}
                    >
                      <Button
                        aria-label={`操作 ${chatbot.name}`}
                        className={ui.chatbotMenu}
                        icon={<MoreOutlined />}
                        type="text"
                      />
                    </Dropdown>
                  </div>
                  <div className={ui.chatbotMetadata}>
                    <Text copyable={{ text: chatbot.id }}>
                      <span className={ui.chatbotId}>ID：{chatbot.id}</span>
                    </Text>
                    <span>
                      最後編輯：{formatLastEditedAt(chatbot.created_at)}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}
      <Modal
        cancelText="取消"
        confirmLoading={creating}
        okText="新增"
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        open={createOpen}
        title="新增 ChatBot"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="ChatBot 名稱"
            name="name"
            rules={[
              { required: true, message: "請輸入 ChatBot 名稱" },
              { max: 200, message: "名稱不可超過 200 個字元" },
            ]}
          >
            <Input autoFocus placeholder="例如：客服 ChatBot" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        cancelText="取消"
        confirmLoading={deleting}
        okButtonProps={{ danger: true }}
        okText="刪除"
        onCancel={() => setPendingDeleteId(null)}
        onOk={handleDelete}
        open={pendingDeleteId !== null}
        title="確定要刪除這個 ChatBot 嗎？"
      >
        <p>刪除後會連同該 ChatBot 的知識庫與相關資料一起移除，且無法復原。</p>
      </Modal>
    </AdminPageLayout>
  );
}
