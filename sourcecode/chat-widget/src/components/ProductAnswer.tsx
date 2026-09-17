import { tw } from "../utils/tw";
import { widgetUi } from "../widgetStyles";

interface ProductAnswerProps {
  text: string;
  source: string | null;
}

export default function ProductAnswer({ text, source }: ProductAnswerProps) {
  return (
    <div className={tw(widgetUi.row, widgetUi.rowBot)}>
      <div className={tw(widgetUi.bubble, widgetUi.bubbleBot)}>
        <p className={widgetUi.bubbleText}>{text}</p>
        {source && (
          <span className={widgetUi.sourceTag}>相關主題：{source}</span>
        )}
      </div>
    </div>
  );
}
