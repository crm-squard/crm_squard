import DatabaseOutlined from "@ant-design/icons/DatabaseOutlined";
import HomeOutlined from "@ant-design/icons/HomeOutlined";
import MenuOutlined from "@ant-design/icons/MenuOutlined";
import ShoppingOutlined from "@ant-design/icons/ShoppingOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import Avatar from "antd/es/avatar";
import Button from "antd/es/button";
import Drawer from "antd/es/drawer";
import Layout from "antd/es/layout";
import Menu from "antd/es/menu";
import Tooltip from "antd/es/tooltip";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import BrandMark from "./BrandMark";

const { Header, Sider, Content } = Layout;
const tenantName = import.meta.env.VITE_TENANT_NAME || "CRM Select Demo";

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
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 900);
  const selectedKey = resolveSelectedKey(location.pathname);

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
          <span>目前租戶</span>
          <strong>{tenantName}</strong>
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
          <div className="account-placeholder" aria-label="帳號功能尚未啟用">
            <Avatar icon={<UserOutlined />} />
            <span><strong>帳號功能</strong><small>敬請期待</small></span>
          </div>
        </Header>
        <Content className="admin-content"><Outlet /></Content>
      </Layout>
    </Layout>
  );
}
