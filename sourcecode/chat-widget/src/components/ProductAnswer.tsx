interface ProductAnswerProps { text: string; source: string | null; }

export default function ProductAnswer({ text, source }: ProductAnswerProps) {
  return (
    <div className="ccw-row ccw-row-bot">
      <div className="ccw-bubble ccw-bubble-bot">
        <p className="ccw-bubble-text">{text}</p>
        {source && <span className="ccw-source-tag">相關主題：{source}</span>}
      </div>
    </div>
  );
}
