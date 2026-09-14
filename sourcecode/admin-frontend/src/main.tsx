import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import ConfigProvider from "antd/es/config-provider";
import zhTW from "antd/locale/zh_TW";
import App from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("找不到 React 掛載節點 #root");

createRoot(root).render(
  <StrictMode>
    <ConfigProvider locale={zhTW} theme={{ token: { colorPrimary: "#1769e0", colorText: "#16213e", colorBgLayout: "#f5f8fc", borderRadius: 12, fontFamily: '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif' }, components: { Menu: { itemBorderRadius: 10, itemHeight: 48 }, Table: { headerBg: "#f7f9fc", headerColor: "#53617a" } } }}>
      <BrowserRouter><App /></BrowserRouter>
    </ConfigProvider>
  </StrictMode>,
);
