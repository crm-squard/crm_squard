import { useState } from "react";
import { MessageCircle } from "lucide-react";
import ChatHeader from "./components/ChatHeader";
import ProviderSelect from "./components/ProviderSelect";
import MessageList from "./components/MessageList";
import ChatComposer from "./components/ChatComposer";
import { useChat } from "./hooks/useChat";
import { useProviders } from "./hooks/useProviders";
import "./chat.css";

const QUICK_REPLIES = ["無線滑鼠支援多少 DPI？", "查詢訂單 A12345", "退貨要幾天內申請？"];

export default function SmartCRMChatWidget() {
  const [isOpen, setIsOpen] = useState(true);
  const [input, setInput] = useState("");
  const { messages, isSending, sendMessage } = useChat();
  const { providers, provider, setProvider } = useProviders();
  function handleSend(text: string) {
    if (sendMessage(text, provider)) setInput("");
  }
  return <div className="ccw-root">
    {isOpen ? <div className="ccw-panel">
      <ChatHeader onClose={() => setIsOpen(false)} />
      <ProviderSelect providers={providers} value={provider} onChange={setProvider} />
      <MessageList messages={messages} isSending={isSending} />
      {messages.length < 2 && <div className="ccw-quick-replies">
        {QUICK_REPLIES.map((question) => <button key={question} className="ccw-chip" onClick={() => handleSend(question)}>
          {question}
        </button>)}
      </div>}
      <ChatComposer value={input} onChange={setInput} onSend={() => handleSend(input)} isSending={isSending} />
    </div> : <button className="ccw-launcher" aria-label="開啟客服聊天視窗" onClick={() => setIsOpen(true)}>
      <MessageCircle size={24} />
    </button>}
  </div>;
}
