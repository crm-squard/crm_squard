import type { ProviderId, ProviderInfo } from "../../../types/api";
interface Props { providers: ProviderInfo[]; value: ProviderId; onChange: (value: ProviderId) => void; }
export default function ProviderSelect({ providers, value, onChange }: Props) {
  return <div className="ccw-model-bar">
    <label htmlFor="ccw-model-select">回答模型</label>
    <select id="ccw-model-select" className="ccw-model-select" value={value} onChange={(event) => {
      const selected = providers.find((entry) => entry.id === event.target.value && entry.configured);
      if (selected) onChange(selected.id);
    }}>
      {providers.map((entry) => <option key={entry.id} value={entry.id} disabled={!entry.configured}>
        {entry.label}{!entry.configured ? "（尚未設定 API key）" : ""}
      </option>)}
    </select>
  </div>;
}
