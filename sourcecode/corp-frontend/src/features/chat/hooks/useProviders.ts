import { useEffect, useState } from "react";
import type { ProviderId, ProviderInfo } from "../../../types/api";
import { fetchProviders } from "../api/chat";

export function useProviders() {
  const [providers, setProviders] = useState<ProviderInfo[]>([
    { id: "google", label: "Google Gemini", configured: true },
  ]);
  const [provider, setProvider] = useState<ProviderId>("google");
  useEffect(() => {
    let active = true;
    void fetchProviders().then((list) => {
      if (!active) return;
      setProviders(list);
      const configured = list.find((entry) => entry.id === "google" && entry.configured) ??
        list.find((entry) => entry.configured);
      if (configured) setProvider(configured.id);
    }).catch(() => {
      // 載入失敗時維持既有預設，避免套用不完整的模型清單。
    });
    return () => { active = false; };
  }, []);
  return { providers, provider, setProvider };
}
