import Button from "antd/es/button";
import Card from "antd/es/card";
import Form from "antd/es/form";
import Input from "antd/es/input";
import List from "antd/es/list";
import message from "antd/es/message";
import Popconfirm from "antd/es/popconfirm";
import Typography from "antd/es/typography";
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { createAccount, deleteAccount, listAccounts } from "../api/accounts";
import type { Account } from "../api/auth";

const { Text, Paragraph } = Typography;

/**
 * 管理者帳號頁籤：只有 platform_primary／platform_secondary 看得到，跟商家帳號完全分開
 * （不會出現在公司設定頁的「管理帳號」清單，也看不到這個頁籤）。新增/移除副管理者僅限
 * platform_primary（比照 ChatbotSettingsPage 商家主帳號能管理次帳號的權限模型）。
 */
export default function AdminAccountsPage() {
  const { token, account: currentAccount } = useAuth();
  const [messageApi, contextHolder] = message.useMessage();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [form] = Form.useForm<{ email: string }>();
  const [adding, setAdding] = useState(false);

  const isPrimary = currentAccount?.role === "platform_primary";

  const loadAccounts = useCallback(() => {
    if (!token) return;
    listAccounts(token)
      .then(setAccounts)
      .catch((err) =>
        messageApi.error(err instanceof Error ? err.message : "帳號清單載入失敗"),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  if (!token) return <Navigate to="/login" replace />;
  if (
    currentAccount &&
    currentAccount.role !== "platform_primary" &&
    currentAccount.role !== "platform_secondary"
  ) {
    return <Navigate to="/" replace />;
  }

  async function handleAdd(values: { email: string }) {
    if (!token) return;
    setAdding(true);
    try {
      await createAccount(token, { email: values.email, role: "platform_secondary" });
      form.resetFields();
      loadAccounts();
      messageApi.success("已新增副管理者帳號");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "新增失敗");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(accountId: string) {
    if (!token) return;
    try {
      await deleteAccount(token, accountId);
      loadAccounts();
      messageApi.success("已移除帳號");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "移除失敗");
    }
  }

  return (
    <main>
      {contextHolder}
      <div>
        <h1>管理者帳號</h1>
        <p>平台維運帳號，預設對所有商家服務都有存取權限，不受單一 Chatbot 綁定限制。</p>
      </div>

      <Card>
        <List
          dataSource={accounts}
          locale={{ emptyText: "目前沒有管理者帳號。" }}
          renderItem={(acc) => (
            <List.Item
              actions={
                isPrimary && acc.id !== currentAccount?.id
                  ? [
                      <Popconfirm
                        key="remove"
                        title="確定要移除這個管理者帳號嗎？"
                        description="移除後該帳號會立刻無法登入。"
                        onConfirm={() => handleRemove(acc.id)}
                      >
                        <Button danger size="small">移除</Button>
                      </Popconfirm>,
                    ]
                  : []
              }
            >
              <List.Item.Meta title={acc.email} description={acc.role} />
            </List.Item>
          )}
        />
        {isPrimary ? (
          <Form form={form} layout="inline" onFinish={handleAdd} style={{ marginTop: 16 }}>
            <Form.Item
              name="email"
              rules={[{ required: true, type: "email", message: "請輸入有效的 gmail 地址" }]}
            >
              <Input placeholder="要新增的副管理者 gmail 地址" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={adding}>
                新增副管理者
              </Button>
            </Form.Item>
          </Form>
        ) : (
          <Paragraph type="secondary" style={{ marginTop: 16 }}>
            只有主管理者帳號能新增/移除副管理者。
          </Paragraph>
        )}
      </Card>
    </main>
  );
}
