import Button from "antd/es/button";
import Card from "antd/es/card";
import Form from "antd/es/form";
import Input from "antd/es/input";
import List from "antd/es/list";
import message from "antd/es/message";
import Popconfirm from "antd/es/popconfirm";
import Typography from "antd/es/typography";
import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ui } from "../uiStyles";
import { deleteCompany, updateCompany } from "../api/companies";
import { createAccount, deleteAccount, listAccounts } from "../api/accounts";
import { listAuditLog, type AuditLogEntry } from "../api/auditLog";
import type { Account } from "../api/auth";

const ACTION_LABELS: Record<string, string> = {
  create_company: "建立商家服務",
  update_company: "更新商家設定",
  delete_company: "刪除商家服務",
  create_account: "新增帳號",
  delete_account: "移除帳號",
  self_register: "帳號自助註冊",
  upsert_document: "上傳/更新知識庫文件",
  delete_document: "刪除知識庫文件",
};

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface CompanySettingsForm {
  name: string;
  mcp_url?: string;
  welcome_message?: string;
  quick_replies?: string;
}

const DEFAULT_QUICK_REPLIES = [
  "無線滑鼠支援多少 DPI？",
  "查詢訂單 A12345",
  "退貨要幾天內申請？",
];

/**
 * 公司資訊設定頁面：MCP URL（訂單查詢用）跟聊天機器人開頭語從原本 select-company 頁面
 * 的就地編輯移過來這裡，select-company 頁面只留商家名稱跟識別碼，操作對象一律是
 * AuthContext 目前選定的公司（跟 RagPage 一樣的模式，不用另外帶 company_id 路由參數）。
 */
export default function CompanySettingsPage() {
  const navigate = useNavigate();
  const {
    token,
    account: currentAccount,
    companies,
    selectedCompanyId,
    selectCompany,
    refreshMe,
  } = useAuth();
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<CompanySettingsForm>();
  const [accountForm] = Form.useForm<{ email: string }>();
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [addingAccount, setAddingAccount] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);

  // 帶 selectedCompanyId：只查這家公司綁定的商家帳號，不含管理者帳號、也不含其他公司的協作帳號。
  const loadAccounts = useCallback(() => {
    if (!token || !selectedCompanyId) return;
    listAccounts(token, selectedCompanyId)
      .then(setAccounts)
      .catch((err) =>
        messageApi.error(
          err instanceof Error ? err.message : "帳號清單載入失敗",
        ),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedCompanyId]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    if (!token || !selectedCompanyId) return;
    listAuditLog(token, selectedCompanyId)
      .then(setAuditEntries)
      .catch((err) =>
        messageApi.error(
          err instanceof Error ? err.message : "稽核紀錄載入失敗",
        ),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedCompanyId]);

  // companies 本來就是 /api/auth/me 依權限回傳的清單（平台角色回全部、商家帳號只回自己
  // 綁定的），能在這個清單裡找到，後端的 require_company_access 就一定會放行，不用在
  // 前端另外判斷角色。
  const company = companies.find((c) => c.id === selectedCompanyId);

  useEffect(() => {
    if (company) {
      form.setFieldsValue({
        name: company.name,
        mcp_url: company.mcp_url ?? "",
        welcome_message: company.welcome_message ?? "",
        quick_replies: (company.quick_replies ?? DEFAULT_QUICK_REPLIES).join(
          "\n",
        ),
      });
    }
  }, [company, form]);

  if (!token) return <Navigate to="/login" replace />;
  if (!selectedCompanyId) return <Navigate to="/select-company" replace />;

  async function handleSave(values: CompanySettingsForm) {
    if (!token || !selectedCompanyId) return;
    setSaving(true);
    try {
      const quickReplies = (values.quick_replies ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
      await updateCompany(token, selectedCompanyId, {
        name: values.name,
        mcp_url: values.mcp_url ?? "",
        welcome_message: values.welcome_message ?? "",
        quick_replies: quickReplies,
      });
      await refreshMe();
      messageApi.success("已儲存公司設定");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddAccount(values: { email: string }) {
    if (!token || !selectedCompanyId) return;
    setAddingAccount(true);
    try {
      await createAccount(token, {
        email: values.email,
        role: "tenant_secondary",
        company_id: selectedCompanyId,
      });
      accountForm.resetFields();
      loadAccounts();
      messageApi.success("已新增管理帳號，該 gmail 登入後即可管理這家商家服務");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "新增失敗");
    } finally {
      setAddingAccount(false);
    }
  }

  async function handleDeleteCompany() {
    if (!token || !selectedCompanyId) return;
    setDeleting(true);
    try {
      await deleteCompany(token, selectedCompanyId);
      selectCompany(null);
      await refreshMe();
      messageApi.success("已刪除商家服務");
      navigate("/select-company", { replace: true });
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "刪除失敗");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRemoveAccount(accountId: string) {
    if (!token || !selectedCompanyId) return;
    try {
      await deleteAccount(token, accountId, selectedCompanyId);
      loadAccounts();
      messageApi.success("已將這個帳號從這家商家服務移除");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "移除失敗");
    }
  }

  const isPlatformRole =
    currentAccount?.role === "platform_primary" ||
    currentAccount?.role === "platform_secondary";
  // 只有這家公司的 primary（或管理者帳號）能新增/移除協作帳號；secondary 看得到清單但不能改。
  const canManageAccounts = isPlatformRole || company?.your_role === "primary";

  return (
    <main>
      {contextHolder}
      <div className={ui.pageHeading}>
        <div>
          <h1>公司設定</h1>
          <p>
            管理目前選定商家的基本資訊、訂單查詢 MCP
            URL、聊天機器人開頭語與開場快速提問。
          </p>
        </div>
      </div>

      <Card>
        {company ? (
          <>
            <Paragraph type="secondary">
              商家識別碼：
              <Text code copyable>
                {company.id}
              </Text>
            </Paragraph>
            <Form form={form} layout="vertical" onFinish={handleSave}>
              <Form.Item
                name="name"
                label="商家名稱"
                rules={[{ required: true, message: "請輸入商家名稱" }]}
              >
                <Input />
              </Form.Item>
              <Form.Item
                name="mcp_url"
                label="訂單查詢 MCP URL"
                extra="沒有填寫時，這家商家的聊天機器人不支援訂單查詢，RAG 知識庫問答不受影響。"
              >
                <Input placeholder="例如 http://localhost:8001/mcp" />
              </Form.Item>
              <Form.Item
                name="welcome_message"
                label="聊天機器人開頭語"
                extra="留空時使用系統預設的開頭語。"
              >
                <TextArea
                  rows={3}
                  placeholder="您好，我是線上客服，可以問我任何產品的規格、特色，或是輸入訂單編號查詢配送狀態喔。"
                />
              </Form.Item>
              <Form.Item
                name="quick_replies"
                label="開場快速提問"
                extra="一行一個，顯示在聊天視窗剛打開時的快速提問按鈕；全部清空時使用系統預設的三個問題。"
              >
                <TextArea
                  rows={3}
                  placeholder={
                    "無線滑鼠支援多少 DPI？\n查詢訂單 A12345\n退貨要幾天內申請？"
                  }
                />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={saving}>
                儲存
              </Button>
            </Form>
            <Popconfirm
              title="確定要刪除這家商家服務嗎？"
              description="會連同這家商家的 RAG 知識庫文件、向量資料一起硬刪除，無法復原。"
              onConfirm={handleDeleteCompany}
              okButtonProps={{ danger: true }}
            >
              <Button className={ui.marginTop4} danger loading={deleting}>
                刪除這家商家服務
              </Button>
            </Popconfirm>
          </>
        ) : (
          <Text type="secondary">查無這家公司的資料。</Text>
        )}
      </Card>

      <Card className={ui.marginTop4} title="管理帳號">
        <Paragraph type="secondary">
          新增的 gmail
          帳號用該帳號登入即可管理這家商家服務（跟你權限相同，差別只在誰能新增/移除誰）。
        </Paragraph>
        <List
          dataSource={accounts}
          locale={{ emptyText: "目前只有你自己在管理這家商家服務。" }}
          renderItem={(acc) => (
            <List.Item
              actions={
                canManageAccounts && acc.id !== currentAccount?.id
                  ? [
                      <Popconfirm
                        key="remove"
                        title="確定要移除這個帳號嗎？"
                        description="移除後該帳號將不再能存取這家商家服務（他其他的商家服務不受影響）。"
                        onConfirm={() => handleRemoveAccount(acc.id)}
                      >
                        <Button danger size="small">
                          移除
                        </Button>
                      </Popconfirm>,
                    ]
                  : []
              }
            >
              <List.Item.Meta
                title={acc.email}
                description={acc.company_role === "primary" ? "主帳號" : "協作帳號"}
              />
            </List.Item>
          )}
        />
        {canManageAccounts ? (
          <Form
            className={ui.marginTop4}
            form={accountForm}
            layout="inline"
            onFinish={handleAddAccount}
          >
            <Form.Item
              name="email"
              rules={[
                {
                  required: true,
                  type: "email",
                  message: "請輸入有效的 gmail 地址",
                },
              ]}
            >
              <Input placeholder="要新增的 gmail 地址" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={addingAccount}>
                新增帳號
              </Button>
            </Form.Item>
          </Form>
        ) : (
          <Paragraph type="secondary" className={ui.marginTop4}>
            只有這家商家服務的主帳號能新增/移除協作帳號。
          </Paragraph>
        )}
      </Card>

      <Card className={ui.marginTop4} title="稽核紀錄">
        <Paragraph type="secondary">
          這家商家服務最近的異動紀錄：建立/刪除、設定變更、知識庫文件、協作帳號新增移除。
        </Paragraph>
        <List
          dataSource={auditEntries}
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
    </main>
  );
}
