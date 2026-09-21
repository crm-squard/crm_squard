import Button from "antd/es/button";
import Card from "antd/es/card";
import Form from "antd/es/form";
import Input from "antd/es/input";
import InputNumber from "antd/es/input-number";
import List from "antd/es/list";
import message from "antd/es/message";
import Popconfirm from "antd/es/popconfirm";
import Switch from "antd/es/switch";
import Typography from "antd/es/typography";
import { useCallback, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import AdminPageLayout from "../components/AdminPageLayout";
import { useAuth } from "../auth/AuthContext";
import { ui } from "../uiStyles";
import {
  deleteChatbot,
  getChatbotMcpToken,
  updateChatbot,
} from "../api/chatbots";
import { createAccount, deleteAccount, listAccounts } from "../api/accounts";
import { listAuditLog, type AuditLogEntry } from "../api/auditLog";
import type { Account } from "../api/auth";

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

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ChatbotSettingsForm {
  name: string;
  mcp_url?: string;
  mcp_token?: string;
  welcome_message?: string;
  quick_replies?: string;
  rag_top_k?: number;
  rerank_enabled?: boolean;
}

// 跟後端 settings.RAG_DEFAULT_TOP_K／RAG_MAX_TOP_K 一致（後端才是最終檢查）
const DEFAULT_RAG_TOP_K = 5;
const MAX_RAG_TOP_K = 10;

const DEFAULT_QUICK_REPLIES = ["無線滑鼠支援多少 DPI？", "退貨要幾天內申請？"];

/**
 * 公司資訊設定頁面：MCP 連線設定（URL 與金鑰，訊息以 @mcp 開頭時使用）跟聊天機器人開頭語從原本 select-chatbot 頁面
 * 的就地編輯移過來這裡，select-chatbot 頁面只留商家名稱跟識別碼，操作對象一律是
 * AuthContext 目前選定的公司（跟 RagPage 一樣的模式，不用另外帶 chatbot_id 路由參數）。
 */
export default function ChatbotSettingsPage() {
  const navigate = useNavigate();
  const {
    token,
    account: currentAccount,
    chatbots,
    selectedChatbotId,
    selectChatbot,
    refreshMe,
  } = useAuth();
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<ChatbotSettingsForm>();
  const [accountForm] = Form.useForm<{ email: string }>();
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  // 金鑰明文只在使用者按下「查看金鑰」後才向後端取得，預設不載入、不顯示；切換公司時清掉。
  const [revealedMcpToken, setRevealedMcpToken] = useState<string | null>(null);
  const [revealingToken, setRevealingToken] = useState(false);
  const [clearingToken, setClearingToken] = useState(false);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [addingAccount, setAddingAccount] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);

  // 帶 selectedChatbotId：只查這家公司綁定的商家帳號，不含管理者帳號、也不含其他公司的協作帳號。
  const loadAccounts = useCallback(() => {
    if (!token || !selectedChatbotId) return;
    listAccounts(token, selectedChatbotId)
      .then(setAccounts)
      .catch((err) =>
        messageApi.error(
          err instanceof Error ? err.message : "帳號清單載入失敗",
        ),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedChatbotId]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    setRevealedMcpToken(null);
  }, [selectedChatbotId]);

  // 公司清單是登入時抓一次、存在瀏覽器裡的快取；別的管理員或別的瀏覽器改了設定（例如 MCP 金鑰），
  // 這裡的資料就會過期（「查看金鑰」按鈕不出現、提示寫「尚未設定」）。打開設定頁時重新向後端取得最新資料。
  useEffect(() => {
    if (!token || !selectedChatbotId) return;
    refreshMe().catch(() => {
      // 重新整理失敗就沿用快取，不打斷頁面
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedChatbotId]);

  useEffect(() => {
    if (!token || !selectedChatbotId) return;
    listAuditLog(token, selectedChatbotId)
      .then(setAuditEntries)
      .catch((err) =>
        messageApi.error(
          err instanceof Error ? err.message : "稽核紀錄載入失敗",
        ),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedChatbotId]);

  // chatbots 本來就是 /api/auth/me 依權限回傳的清單（平台角色回全部、商家帳號只回自己
  // 綁定的），能在這個清單裡找到，後端的 require_chatbot_access 就一定會放行，不用在
  // 前端另外判斷角色。
  const chatbot = chatbots.find((c) => c.id === selectedChatbotId);

  useEffect(() => {
    if (chatbot) {
      form.setFieldsValue({
        name: chatbot.name,
        mcp_url: chatbot.mcp_url ?? "",
        welcome_message: chatbot.welcome_message ?? "",
        quick_replies: (chatbot.quick_replies ?? DEFAULT_QUICK_REPLIES).join(
          "\n",
        ),
        rag_top_k: chatbot.rag_top_k ?? DEFAULT_RAG_TOP_K,
        rerank_enabled: chatbot.rerank_enabled ?? false,
      });
    }
  }, [chatbot, form]);

  if (!token) return <Navigate to="/login" replace />;
  if (!selectedChatbotId) return <Navigate to="/select-chatbot" replace />;

  async function handleSave(values: ChatbotSettingsForm) {
    if (!token || !selectedChatbotId) return;
    setSaving(true);
    try {
      const quickReplies = (values.quick_replies ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
      await updateChatbot(token, selectedChatbotId, {
        name: values.name,
        mcp_url: values.mcp_url ?? "",
        // 金鑰欄位留空代表不變更（空字串在後端是「清除」，改由專用的清除按鈕處理）
        ...(values.mcp_token ? { mcp_token: values.mcp_token } : {}),
        welcome_message: values.welcome_message ?? "",
        quick_replies: quickReplies,
        rag_top_k: values.rag_top_k ?? DEFAULT_RAG_TOP_K,
        // 只有開關真的被改動才送出：伺服器不支援 rerank 時，後端會拒絕「開啟」，
        // 若資料庫裡本來就是開啟（本機與正式共用資料庫），每次儲存都帶 true 會讓整個儲存失敗。
        ...(!!values.rerank_enabled !== !!chatbot?.rerank_enabled
          ? { rerank_enabled: !!values.rerank_enabled }
          : {}),
      });
      form.setFieldValue("mcp_token", "");
      setRevealedMcpToken(null);
      await refreshMe();
      messageApi.success("已儲存 Chatbot 設定");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  async function handleRevealMcpToken() {
    if (!token || !selectedChatbotId) return;
    setRevealingToken(true);
    try {
      setRevealedMcpToken(
        (await getChatbotMcpToken(token, selectedChatbotId)) ?? "",
      );
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "查看金鑰失敗");
    } finally {
      setRevealingToken(false);
    }
  }

  async function handleClearMcpToken() {
    if (!token || !selectedChatbotId) return;
    setClearingToken(true);
    try {
      await updateChatbot(token, selectedChatbotId, { mcp_token: "" });
      setRevealedMcpToken(null);
      await refreshMe();
      messageApi.success("已清除 MCP 金鑰");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "清除金鑰失敗");
    } finally {
      setClearingToken(false);
    }
  }

  async function handleAddAccount(values: { email: string }) {
    if (!token || !selectedChatbotId) return;
    setAddingAccount(true);
    try {
      await createAccount(token, {
        email: values.email,
        role: "tenant_secondary",
        chatbot_id: selectedChatbotId,
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

  async function handleDeleteChatbot() {
    if (!token || !selectedChatbotId) return;
    setDeleting(true);
    try {
      await deleteChatbot(token, selectedChatbotId);
      selectChatbot(null);
      await refreshMe();
      messageApi.success("已刪除商家服務");
      navigate("/select-chatbot", { replace: true });
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "刪除失敗");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRemoveAccount(accountId: string) {
    if (!token || !selectedChatbotId) return;
    try {
      await deleteAccount(token, accountId, selectedChatbotId);
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
  const canManageAccounts = isPlatformRole || chatbot?.your_role === "primary";

  return (
    <AdminPageLayout
      title="Chatbot 設定"
      description="管理目前選定商家的基本資訊、MCP 連線設定（URL 與金鑰）、聊天機器人開頭語與開場快速提問。"
      beforeHeader={contextHolder}
    >
      <Card>
        {chatbot ? (
          <>
            <Paragraph type="secondary">
              商家識別碼：
              <Text code copyable>
                {chatbot.id}
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
                label="MCP URL"
                extra="使用者訊息以 @mcp 開頭時，聊天機器人會透過這個位址的 MCP server 呼叫查詢功能（支援 Gemini 與本地模型）。沒有填寫時 @mcp 不可用，RAG 知識庫問答不受影響。"
              >
                <Input placeholder="例如 http://localhost:8001/mcp" />
              </Form.Item>
              <Form.Item
                name="mcp_token"
                label="MCP 金鑰"
                extra="呼叫這家商家的 MCP server 時使用的 Bearer 金鑰。留空表示不變更；已設定的金鑰可用下方按鈕查看（每次查看都會寫入稽核紀錄）。"
              >
                <Input.Password
                  autoComplete="new-password"
                  placeholder={
                    chatbot.has_mcp_token
                      ? "已設定，留空表示不變更"
                      : "尚未設定"
                  }
                />
              </Form.Item>
              {chatbot.has_mcp_token ? (
                <Form.Item>
                  <div className={ui.inlineActions}>
                    {revealedMcpToken === null ? (
                      <Button
                        loading={revealingToken}
                        onClick={handleRevealMcpToken}
                      >
                        查看金鑰
                      </Button>
                    ) : (
                      <>
                        <Text code copyable>
                          {revealedMcpToken}
                        </Text>
                        <Button onClick={() => setRevealedMcpToken(null)}>
                          隱藏
                        </Button>
                      </>
                    )}
                    <Popconfirm
                      title="確定要清除這家商家的 MCP 金鑰嗎？"
                      description="清除後 @mcp 會因為金鑰無效而無法連線，直到重新設定。"
                      onConfirm={handleClearMcpToken}
                      okButtonProps={{ danger: true }}
                    >
                      <Button danger loading={clearingToken}>
                        清除金鑰
                      </Button>
                    </Popconfirm>
                  </div>
                </Form.Item>
              ) : null}
              <Form.Item
                name="welcome_message"
                label="聊天機器人開頭語"
                extra="留空時使用系統預設的開頭語。"
              >
                <TextArea
                  rows={3}
                  placeholder="您好，我是線上客服，可以問我任何產品的規格、特色，或是退換貨政策喔。"
                />
              </Form.Item>
              <Form.Item
                name="quick_replies"
                label="開場快速提問"
                extra="一行一個，顯示在聊天視窗剛打開時的快速提問按鈕；全部清空時使用系統預設的問題。"
              >
                <TextArea
                  rows={3}
                  placeholder={"無線滑鼠支援多少 DPI？\n退貨要幾天內申請？"}
                />
              </Form.Item>
              <Form.Item
                name="rag_top_k"
                label="檢索片段數（k）"
                extra={`每次回答時，從知識庫挑幾段內容交給 AI 參考（1～${MAX_RAG_TOP_K}，預設 ${DEFAULT_RAG_TOP_K}）。`}
                rules={[{ required: true, message: "請輸入片段數" }]}
              >
                <InputNumber min={1} max={MAX_RAG_TOP_K} precision={0} />
              </Form.Item>
              <Form.Item
                name="rerank_enabled"
                label="重排序（rerank）"
                valuePropName="checked"
                extra={
                  chatbot.rerank_available
                    ? "先從知識庫撈一批候選（預設 20 段），再用重排序模型挑出最相關的 k 段。每段候選都要跑一次模型，每次回答會多花約 5 秒，且效果尚未經過評估。"
                    : "這個環境不支援重排序（正式環境無法使用），目前一律使用一般檢索。"
                }
              >
                <Switch
                  disabled={
                    !chatbot.rerank_available && !chatbot.rerank_enabled
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
              onConfirm={handleDeleteChatbot}
              okButtonProps={{ danger: true }}
            >
              <Button className={ui.marginTop4} danger loading={deleting}>
                刪除這家商家服務
              </Button>
            </Popconfirm>
          </>
        ) : (
          <Text type="secondary">查無這個 Chatbot 的資料。</Text>
        )}
      </Card>

      <Card title="管理帳號">
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
                description={
                  acc.chatbot_role === "primary" ? "主帳號" : "協作帳號"
                }
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

      <Card title="稽核紀錄">
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
    </AdminPageLayout>
  );
}
