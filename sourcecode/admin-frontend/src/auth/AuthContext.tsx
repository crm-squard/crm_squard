import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  getMe,
  loginWithDevAccount,
  loginWithGoogle,
  logout as logoutApi,
} from "../api/auth";
import { setUnauthorizedHandler } from "../api/apiClient";
import type { Account, ChatbotInfo } from "../types/auth";

const STORAGE_KEY = "admin_auth_state";

interface PersistedAuthState {
  token: string | null;
  selectedChatbotId: string | null;
}

interface AuthState extends PersistedAuthState {
  account: Account | null;
  chatbots: ChatbotInfo[];
}

const EMPTY_STATE: AuthState = {
  token: null,
  account: null,
  chatbots: [],
  selectedChatbotId: null,
};

// token 是可撤銷的 opaque session token（非密碼），存 localStorage 讓重整頁面不用重新登入，
// 符合現有系統的信任模型。
function loadStoredState(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STATE;
    const parsed = JSON.parse(raw) as Partial<PersistedAuthState>;
    return {
      token: parsed.token ?? null,
      account: null,
      chatbots: [],
      selectedChatbotId: parsed.selectedChatbotId ?? null,
    };
  } catch {
    return EMPTY_STATE;
  }
}

function persistState(state: PersistedAuthState) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      token: state.token,
      selectedChatbotId: state.selectedChatbotId,
    } satisfies PersistedAuthState),
  );
}

interface AuthContextValue {
  token: string | null;
  account: Account | null;
  chatbots: ChatbotInfo[];
  selectedChatbotId: string | null;
  isInitializing: boolean;
  initializationError: string | null;
  loginWithIdToken: (idToken: string) => Promise<void>;
  loginWithDev: () => Promise<void>;
  logout: () => Promise<void>;
  selectChatbot: (chatbotId: string | null) => void;
  refreshMe: () => Promise<void>;
  retryInitialization: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => loadStoredState());
  const [isInitializing, setIsInitializing] = useState(
    () => Boolean(state.token) && !state.account,
  );
  const [initializationError, setInitializationError] = useState<string | null>(
    null,
  );
  const [initializationKey, setInitializationKey] = useState(0);

  const updateState = useCallback((next: AuthState) => {
    setState(next);
    persistState(next);
  }, []);

  useLayoutEffect(() => {
    if (!state.token) return;
    return setUnauthorizedHandler(() => updateState(EMPTY_STATE));
  }, [state.token, updateState]);

  useEffect(() => {
    if (!state.token || state.account) {
      setIsInitializing(false);
      setInitializationError(null);
      return;
    }

    const token = state.token;
    let isCurrent = true;
    setIsInitializing(true);
    setInitializationError(null);

    getMe(token)
      .then((me) => {
        if (!isCurrent) return;
        setState((current) => {
          if (current.token !== token) return current;
          const selectedChatbotId = me.chatbots.some(
            (chatbot) => chatbot.id === current.selectedChatbotId,
          )
            ? current.selectedChatbotId
            : null;
          const next: AuthState = {
            ...current,
            account: me.account,
            chatbots: me.chatbots,
            selectedChatbotId,
          };
          persistState(next);
          return next;
        });
      })
      .catch((error: unknown) => {
        if (!isCurrent) return;
        setInitializationError(
          error instanceof Error
            ? error.message
            : "無法驗證登入狀態，請稍後再試。",
        );
      })
      .finally(() => {
        if (isCurrent) setIsInitializing(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [initializationKey, state.account, state.token]);

  const retryInitialization = useCallback(() => {
    setInitializationKey((key) => key + 1);
  }, []);

  const loginWithIdToken = useCallback(
    async (idToken: string) => {
      const { token, account } = await loginWithGoogle(idToken);
      const me = await getMe(token);
      updateState({
        token,
        account: me.account,
        chatbots: me.chatbots,
        selectedChatbotId: null,
      });
      void account; // getMe 回傳的 account 已含相同資訊，登入回應僅用於取得 token
    },
    [updateState],
  );

  // 開發用一鍵登入：只在開發模式的登入頁顯示入口，後端另有多重限制（見 backend/app/main.py）
  const loginWithDev = useCallback(async () => {
    const { token } = await loginWithDevAccount();
    const me = await getMe(token);
    updateState({
      token,
      account: me.account,
      chatbots: me.chatbots,
      selectedChatbotId: null,
    });
  }, [updateState]);

  const logout = useCallback(async () => {
    if (state.token) {
      try {
        await logoutApi(state.token);
      } catch {
        // 後端撤銷失敗也要清掉本機狀態，避免使用者卡在已登入畫面
      }
    }
    updateState(EMPTY_STATE);
  }, [state.token, updateState]);

  const selectChatbot = useCallback(
    (chatbotId: string | null) => {
      updateState({ ...state, selectedChatbotId: chatbotId });
    },
    [state, updateState],
  );

  const refreshMe = useCallback(async () => {
    if (!state.token) return;
    const me = await getMe(state.token);
    updateState({ ...state, account: me.account, chatbots: me.chatbots });
  }, [state, updateState]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token: state.token,
      account: state.account,
      chatbots: state.chatbots,
      selectedChatbotId: state.selectedChatbotId,
      isInitializing,
      initializationError,
      loginWithIdToken,
      loginWithDev,
      logout,
      selectChatbot,
      refreshMe,
      retryInitialization,
    }),
    [
      state,
      isInitializing,
      initializationError,
      loginWithIdToken,
      loginWithDev,
      logout,
      selectChatbot,
      refreshMe,
      retryInitialization,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必須在 AuthProvider 內使用");
  return ctx;
}
