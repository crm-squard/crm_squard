import Alert from "antd/es/alert";
import Spin from "antd/es/spin";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import BrandMark from "../components/BrandMark";
import { useAuth } from "../auth/AuthContext";
import { ui } from "../uiStyles";

// Google Identity Services 由 index.html 的 <script> 標籤載入，型別上補一個最小宣告即可，
// 不需要額外安裝 @types 套件。
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, unknown>,
          ) => void;
        };
      };
    };
  }
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { loginWithIdToken } = useAuth();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  useEffect(() => {
    if (!clientId || !buttonRef.current) return;

    async function handleCredential(response: { credential: string }) {
      setLoading(true);
      setError(null);
      try {
        await loginWithIdToken(response.credential);
        navigate("/select-chatbot", { replace: true });
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "登入失敗，請確認帳號是否已被授權",
        );
      } finally {
        setLoading(false);
      }
    }

    // GSI script 是 async defer 載入，理論上此時已可用；若尚未就緒就略過，避免拋例外。
    if (!window.google) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCredential,
    });
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
    });
  }, [clientId, loginWithIdToken, navigate]);

  return (
    <main className={ui.centeredPage}>
      <div className={ui.loginCard}>
        <BrandMark />
        <h1>管理後台登入</h1>
        <p>請使用已授權的 Google 帳號登入。</p>
        {!clientId ? (
          <Alert
            type="warning"
            showIcon
            message="尚未設定 VITE_GOOGLE_CLIENT_ID，無法顯示 Google 登入按鈕"
          />
        ) : null}
        {error ? <Alert type="error" showIcon message={error} /> : null}
        {loading ? <Spin /> : <div ref={buttonRef} />}
      </div>
    </main>
  );
}
