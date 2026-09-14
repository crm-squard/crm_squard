import { useRef, useState } from "react";
import type { ProviderId } from "../../../types/api";
import { askBackend } from "../api/chat";
import type { ChatMessage } from "../types";
import { buildHistory, toChatMessage } from "../utils/messages";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    role: "bot", type: "text",
    text: "您好，我是線上客服，可以問我任何產品的規格、特色，或是輸入訂單編號查詢配送狀態喔。",
  }]);
  const [isSending, setIsSending] = useState(false);
  const sendingRef = useRef(false);

  function sendMessage(text: string, provider: ProviderId): boolean {
    const trimmed = text.trim();
    if (!trimmed || sendingRef.current) return false;
    const history = buildHistory(messages);
    // 同一個 render 內連續送出時，state 尚未更新，需同步阻止重複請求。
    sendingRef.current = true;
    setIsSending(true);
    setMessages((previous) => [...previous, { role: "user", type: "text", text: trimmed }]);
    void askBackend({ message: trimmed, history, provider })
      .then((response) => {
        const message = toChatMessage(response);
        setMessages((previous) => [...previous, message]);
      })
      .catch((error: unknown) => {
        console.error("[askBackend 呼叫失敗]", error);
        setMessages((previous) => [...previous, {
          role: "bot", type: "text",
          text: "客服暫時無法連線，請確認後端服務是否已啟動，或稍後再試一次。",
        }]);
      })
      .finally(() => {
        sendingRef.current = false;
        setIsSending(false);
      });
    return true;
  }

  return { messages, isSending, sendMessage };
}
