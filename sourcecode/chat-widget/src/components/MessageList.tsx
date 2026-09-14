import { useEffect, useRef } from "react";
import type { ChatMessage } from "../types";
import { assertNever } from "../utils/messages";
import ProductAnswer from "./ProductAnswer";
import OrderCard from "./OrderCard";
import TypingIndicator from "./TypingIndicator";

function Message({ message }: { message: ChatMessage }) {
  switch (message.type) {
    case "text":
      return <div className={message.role === "user" ? "ccw-row ccw-row-user" : "ccw-row ccw-row-bot"}>
        <div className={message.role === "user" ? "ccw-bubble ccw-bubble-user" : "ccw-bubble ccw-bubble-bot"}>
          <p className="ccw-bubble-text">{message.text}</p>
        </div>
      </div>;
    case "product":
      return <ProductAnswer text={message.text} source={message.source} />;
    case "order":
      return <OrderCard code={message.code} status={message.status} eta={message.eta} items={message.items} />;
    default:
      return assertNever(message);
  }
}
export default function MessageList({ messages, isSending }: { messages: ChatMessage[]; isSending: boolean }) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, isSending]);
  return <div className="ccw-messages" ref={listRef}>
    {messages.map((message, index) => <Message key={index} message={message} />)}
    {isSending && <TypingIndicator />}
  </div>;
}
