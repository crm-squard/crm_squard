import CustomerServiceOutlined from "@ant-design/icons/CustomerServiceOutlined";
import DatabaseOutlined from "@ant-design/icons/DatabaseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import HomeOutlined from "@ant-design/icons/HomeOutlined";
import LogoutOutlined from "@ant-design/icons/LogoutOutlined";
import MenuOutlined from "@ant-design/icons/MenuOutlined";
import SettingOutlined from "@ant-design/icons/SettingOutlined";
import ShoppingOutlined from "@ant-design/icons/ShoppingOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
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
import { ui } from "../uiStyles";

const { Header, Sider, Content } = Layout;

// 公司設定排第一個（使用者明確要求：進到後台第一眼要能設定/確認目前是哪家公司）。
const navigationItems = [
  { key: "/company-settings", icon: <SettingOutlined />, label: "公司設定" },
  { key: "/", icon: <HomeOutlined />, label: "儀表板" },
  { key: "/orders", icon: <ShoppingOutlined />, label: "訂單管理" },
  { key: "/rag", icon: <DatabaseOutlined />, label: "RAG 知識庫" },
  { key: "/summary", icon: <CustomerServiceOutlined />, label: "客服機器人" },
];

// 「管理者帳號」頁籤只給 platform_primary／platform_secondary 看，商家帳號完全看不到這個入口。
const ADMIN_ACCOUNTS_ITEM = {
  key: "/admin-accounts",
  icon: <TeamOutlined />,
  label: "管理者帳號",
};

function resolveSelectedKey(pathname: string) {
  if (pathname.startsWith("/orders")) return "/orders";
  if (pathname.startsWith("/rag")) return "/rag";
  if (pathname.startsWith("/company-settings")) return "/company-settings";
  if (pathname.startsWith("/summary")) return "/summary";
  if (pathname.startsWith("/admin-accounts")) return "/admin-accounts";
  return "/";
}

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { account, companies, selectedCompanyId, selectCompany, logout } =
    useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 900);
  const selectedKey = resolveSelectedKey(location.pathname);
  const selectedCompany = companies.find(
    (company) => company.id === selectedCompanyId,
  );
  const isPlatformRole =
    account?.role === "platform_primary" || account?.role === "platform_secondary";
  const menuItems = isPlatformRole
    ? [...navigationItems, ADMIN_ACCOUNTS_ITEM]
    : navigationItems;

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
      <div className={ui.siderBrand}>
        <BrandMark compact={collapsed && !isMobile} />
      </div>
      {(!collapsed || isMobile) && (
        <div className={ui.tenantBlock}>
          <span>目前商家</span>
          {companies.length > 1 ? (
            <Dropdown
              menu={{
                items: companies.map((company) => ({
                  key: company.id,
                  label: company.name,
                })),
                onClick: ({ key }) => selectCompany(key),
              }}
            >
              <strong className={ui.tenantSwitcher}>
                {selectedCompany?.name ?? "選擇商家"} <DownOutlined />
              </strong>
            </Dropdown>
          ) : (
            <strong>{selectedCompany?.name ?? "-"}</strong>
          )}
          {/* 只有一家公司時上面沒有下拉選單，這裡另外給一個固定入口，不然新增第二家商家後
              就永遠回不到選公司頁面了（選了一家之後 CompanySelectPage 不會再自動出現）。 */}
          <button
            type="button"
            className={ui.tenantManageLink}
            onClick={() => navigate("/select-company")}
          >
            管理商家服務
          </button>
        </div>
      )}
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        inlineCollapsed={collapsed && !isMobile}
        onClick={({ key }) => {
          navigate(key);
          setMobileOpen(false);
        }}
      />
      {(!collapsed || isMobile) && (
        <div className={ui.siderCaption}>
          CRM Console
          <br />
          v0.1.0
        </div>
      )}
    </>
  );

  return (
    <Layout className={ui.adminShell}>
      {!isMobile && (
        <Sider
          width={224}
          collapsedWidth={76}
          collapsed={collapsed}
          theme="light"
          className={ui.desktopSider}
        >
          {navigation}
        </Sider>
      )}
      <Drawer
        placement="left"
        width={260}
        open={isMobile && mobileOpen}
        onClose={() => setMobileOpen(false)}
        closable={false}
        classNames={{ body: "p-0!" }}
      >
        <div className={ui.mobileNavigation}>{navigation}</div>
      </Drawer>
      <Layout>
        <Header className={ui.adminHeader}>
          <Tooltip
            title={isMobile ? "開啟選單" : collapsed ? "展開選單" : "收合選單"}
          >
            <Button
              className={ui.menuToggle}
              type="text"
              icon={<MenuOutlined />}
              aria-label={
                isMobile ? "開啟選單" : collapsed ? "展開選單" : "收合選單"
              }
              onClick={() =>
                isMobile ? setMobileOpen(true) : setCollapsed((value) => !value)
              }
            />
          </Tooltip>
          <Dropdown
            menu={{
              items: [
                { key: "logout", icon: <LogoutOutlined />, label: "登出" },
              ],
              onClick: ({ key }) => {
                if (key === "logout") handleLogout();
              },
            }}
          >
            <div className={ui.account} aria-label="帳號選單">
              <Avatar icon={<UserOutlined />} />
              <span>
                <strong>{account?.email ?? "-"}</strong>
                <small>{account?.role ?? ""}</small>
              </span>
            </div>
          </Dropdown>
        </Header>
        <Content className={ui.adminContent}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
