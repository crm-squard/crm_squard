import { useLayoutEffect, useRef, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isSending: boolean;
}
export default function ChatComposer({ value, onChange, onSend, isSending }: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const composingRef = useRef(false);
  useLayoutEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const maxHeight = Number.parseFloat(getComputedStyle(textarea).maxHeight);
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [value]);
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const composing = composingRef.current || event.nativeEvent.isComposing || event.keyCode === 229;
    if (event.key === "Enter" && !event.shiftKey && !composing) {
      event.preventDefault();
      onSend();
    }
  }
  return <div className="ccw-input-bar">
    <textarea ref={inputRef} rows={1} className="ccw-input" value={value}
      placeholder="輸入您的問題或訂單編號…"
      onChange={(event) => onChange(event.target.value)} onKeyDown={handleKeyDown}
      onCompositionStart={() => { composingRef.current = true; }}
      onCompositionEnd={() => { composingRef.current = false; }} aria-label="輸入訊息" />
    <button className="ccw-send-btn" onClick={onSend} disabled={!value.trim() || isSending} aria-label="送出訊息">
      <Send size={16} />
    </button>
  </div>;
}
