import DatabaseOutlined from "@ant-design/icons/DatabaseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import HomeOutlined from "@ant-design/icons/HomeOutlined";
import LogoutOutlined from "@ant-design/icons/LogoutOutlined";
import MenuOutlined from "@ant-design/icons/MenuOutlined";
import ShoppingOutlined from "@ant-design/icons/ShoppingOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import Avatar from "antd/es/avatar";
import Button from "antd/es/button";
import Drawer from "antd/es/drawer";
import Dropdown from "antd/es/dropdown";
import Layout from "antd/es/layout";
import Menu from "antd/es/menu";
import Tooltip from "antd/es/tooltip";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import BrandMark from "./BrandMark";
import { useAuth } from "../auth/AuthContext";

const { Header, Sider, Content } = Layout;

const navigationItems = [
  { key: "/", icon: <HomeOutlined />, label: "儀表板" },
  { key: "/orders", icon: <ShoppingOutlined />, label: "訂單管理" },
  { key: "/rag", icon: <DatabaseOutlined />, label: "RAG 知識庫" },
];

function resolveSelectedKey(pathname: string) {
  if (pathname.startsWith("/orders")) return "/orders";
  if (pathname.startsWith("/rag")) return "/rag";
  return "/";
}

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { account, companies, selectedCompanyId, selectCompany, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 900);
  const selectedKey = resolveSelectedKey(location.pathname);
  const selectedCompany = companies.find((company) => company.id === selectedCompanyId);

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  useEffect(() => {
    const media = window.matchMedia("(max-width: 899px)");
    const handleChange = () => setIsMobile(media.matches);
    handleChange();
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, []);

  const navigation = (
    <>
      <div className="sider-brand"><BrandMark compact={collapsed && !isMobile} /></div>
      {(!collapsed || isMobile) && (
        <div className="tenant-block">
          <span>目前商家</span>
          {companies.length > 1 ? (
            <Dropdown
              menu={{
                items: companies.map((company) => ({ key: company.id, label: company.name })),
                onClick: ({ key }) => selectCompany(key),
              }}
            >
              <strong className="tenant-switcher">{selectedCompany?.name ?? "選擇商家"} <DownOutlined /></strong>
            </Dropdown>
          ) : (
            <strong>{selectedCompany?.name ?? "-"}</strong>
          )}
        </div>
      )}
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={navigationItems}
        inlineCollapsed={collapsed && !isMobile}
        onClick={({ key }) => {
          navigate(key);
          setMobileOpen(false);
        }}
      />
      {(!collapsed || isMobile) && <div className="sider-caption">CRM Console<br />v0.1.0</div>}
    </>
  );

  return (
    <Layout className="admin-shell">
      {!isMobile && (
        <Sider width={224} collapsedWidth={76} collapsed={collapsed} theme="light" className="desktop-sider">
          {navigation}
        </Sider>
      )}
      <Drawer placement="left" width={260} open={isMobile && mobileOpen} onClose={() => setMobileOpen(false)} closable={false} styles={{ body: { padding: 0 } }}>
        <div className="mobile-navigation">{navigation}</div>
      </Drawer>
      <Layout>
        <Header className="admin-header">
          <Tooltip title={isMobile ? "開啟選單" : collapsed ? "展開選單" : "收合選單"}>
            <Button
              className="menu-toggle"
              type="text"
              icon={<MenuOutlined />}
              aria-label={isMobile ? "開啟選單" : collapsed ? "展開選單" : "收合選單"}
              onClick={() => isMobile ? setMobileOpen(true) : setCollapsed((value) => !value)}
            />
          </Tooltip>
          <Dropdown
            menu={{
              items: [{ key: "logout", icon: <LogoutOutlined />, label: "登出" }],
              onClick: ({ key }) => { if (key === "logout") handleLogout(); },
            }}
          >
            <div className="account-placeholder" aria-label="帳號選單">
              <Avatar icon={<UserOutlined />} />
              <span><strong>{account?.email ?? "-"}</strong><small>{account?.role ?? ""}</small></span>
            </div>
          </Dropdown>
        </Header>
        <Content className="admin-content"><Outlet /></Content>
      </Layout>
    </Layout>
  );
}
