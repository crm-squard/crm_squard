import Button from "antd/es/button";
import Card from "antd/es/card";
import Form from "antd/es/form";
import Input from "antd/es/input";
import List from "antd/es/list";
import message from "antd/es/message";
import Space from "antd/es/space";
import Typography from "antd/es/typography";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import BrandMark from "../components/BrandMark";
import { useAuth } from "../auth/AuthContext";
import { createCompany, updateCompany } from "../api/companies";
import type { CompanyInfo } from "../api/auth";

const { Text } = Typography;

function isPlatformRole(role: string | undefined): boolean {
  return role === "platform_primary" || role === "platform_secondary";
}

function CompanyMcpUrlEditor({ company, token, onUpdated }: { company: CompanyInfo; token: string; onUpdated: (company: CompanyInfo) => void }) {
  const [messageApi, contextHolder] = message.useMessage();
  const [value, setValue] = useState(company.mcp_url ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await updateCompany(token, company.id, { mcp_url: value });
      onUpdated(updated);
      messageApi.success("已更新 MCP URL");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "更新失敗");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Space>
      {contextHolder}
      <Input
        placeholder="mcp_url（選填，未設定則不支援訂單查詢）"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        style={{ width: 320 }}
      />
      <Button size="small" loading={saving} onClick={handleSave}>儲存</Button>
    </Space>
  );
}

export default function CompanySelectPage() {
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const { token, account, companies, selectedCompanyId, selectCompany, refreshMe } = useAuth();
  const [creating, setCreating] = useState(false);
  const [companyList, setCompanyList] = useState<CompanyInfo[]>(companies);
  const [form] = Form.useForm<{ name: string; mcp_url?: string }>();

  useEffect(() => {
    setCompanyList(companies);
  }, [companies]);

  // 只有一家公司時沒有「選擇」的意義，自動選定並跳過此頁。
  useEffect(() => {
    if (companyList.length === 1 && !selectedCompanyId) {
      selectCompany(companyList[0].id);
    }
  }, [companyList, selectedCompanyId, selectCompany]);

  if (!token) return <Navigate to="/login" replace />;
  // 只有 selectedCompanyId 真的被設定後才導向主畫面；只憑 companyList.length === 1
  // 就導頁的話，會搶在上面的 useEffect 呼叫 selectCompany 之前跳走，
  // 導致 selectedCompanyId 永遠沒被設定、被 RequireAuth 導回本頁造成循環。
  if (selectedCompanyId) {
    return <Navigate to="/" replace />;
  }

  async function handleCreate(values: { name: string; mcp_url?: string }) {
    if (!token) return;
    setCreating(true);
    try {
      await createCompany(token, { name: values.name, mcp_url: values.mcp_url || undefined });
      await refreshMe();
      form.resetFields();
      messageApi.success("已新增商家服務");
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : "新增失敗");
    } finally {
      setCreating(false);
    }
  }

  function handleCompanyUpdated(updated: CompanyInfo) {
    setCompanyList((prev) => prev.map((company) => (company.id === updated.id ? updated : company)));
  }

  return (
    <main className="company-select-page">
      {contextHolder}
      <div className="company-select-card">
        <BrandMark />
        <h1>選擇要管理的商家</h1>
        {companyList.length === 0 ? (
          <Text type="secondary">目前沒有可管理的商家，請聯繫平台管理員。</Text>
        ) : (
          <List
            dataSource={companyList}
            renderItem={(company) => {
              const canEdit = isPlatformRole(account?.role);
              return (
                <List.Item
                  actions={[
                    <Button key="select" type="primary" onClick={() => { selectCompany(company.id); navigate("/", { replace: true }); }}>
                      選擇
                    </Button>,
                  ]}
                >
                  <List.Item.Meta title={company.name} description={canEdit && token ? <CompanyMcpUrlEditor company={company} token={token} onUpdated={handleCompanyUpdated} /> : (company.mcp_url || "未設定 mcp_url")} />
                </List.Item>
              );
            }}
          />
        )}

        {isPlatformRole(account?.role) ? (
          <Card size="small" title="新增商家服務" className="company-create-card">
            <Form form={form} layout="inline" onFinish={handleCreate}>
              <Form.Item name="name" rules={[{ required: true, message: "請輸入商家名稱" }]}>
                <Input placeholder="商家名稱" />
              </Form.Item>
              <Form.Item name="mcp_url">
                <Input placeholder="mcp_url（選填）" style={{ width: 280 }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={creating}>新增</Button>
              </Form.Item>
            </Form>
          </Card>
        ) : null}
      </div>
    </main>
  );
}
