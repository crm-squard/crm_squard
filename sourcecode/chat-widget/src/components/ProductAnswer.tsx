import { useState } from "react";
import type { SourceRef } from "../api-types";
import { tw } from "../utils/tw";
import { widgetUi } from "../widgetStyles";

interface ProductAnswerProps {
  text: string;
  sources: SourceRef[] | null;
}

// 後端回傳的是向量距離（越低越相關），轉成 0–100 的相關分數方便閱讀。
function toScore(distance: number): number {
  return Math.round(Math.min(1, Math.max(0, 1 - distance)) * 100);
}

export default function ProductAnswer({ text, sources }: ProductAnswerProps) {
  const [expanded, setExpanded] = useState(false);
  // 分數由高到低（距離由小到大）；複製一份避免改動原訊息資料。
  const topics = [...(sources ?? [])].sort((a, b) => a.distance - b.distance);
  const toggle = (
    <button
      type="button"
      className={tw(widgetUi.sourceTag, "cursor-pointer border-0")}
      aria-expanded={expanded}
      onClick={() => setExpanded((value) => !value)}
    >
      相關主題（{topics.length}）{expanded ? "▲" : "▼"}
    </button>
  );
  return (
    <div className={tw(widgetUi.row, widgetUi.rowBot)}>
      <div className={tw(widgetUi.bubble, widgetUi.bubbleBot)}>
        <p className={widgetUi.bubbleText}>{text}</p>
        {topics.length > 0 ? (
          <div>
            {toggle}
            {expanded && (
              <>
                <ul className="m-0 mt-2 list-none p-0">
                  {topics.map((item, index) => (
                    <li
                      key={index}
                      className="flex justify-between gap-2 text-label text-widget-muted"
                    >
                      <span>{item.topic || item.source}</span>
                      <span>{toScore(item.distance)} 分</span>
                    </li>
                  ))}
                </ul>
                {toggle}
              </>
            )}
          </div>
        ) : (
          <span className={widgetUi.sourceTag}>相關主題：無</span>
        )}
      </div>
    </div>
  );
}
