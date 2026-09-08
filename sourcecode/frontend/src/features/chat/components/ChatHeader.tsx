import { Sparkles, X } from "lucide-react";
export default function ChatHeader({ onClose }: { onClose: () => void }) {
  return <div className="ccw-header">
    <div className="ccw-header-brand"><div className="ccw-header-icon"><Sparkles size={17} /></div>
      <div><div className="ccw-header-title">智慧家電客服</div>
        <div className="ccw-header-status"><span className="ccw-status-dot" />線上服務中</div>
      </div>
    </div>
    <button className="ccw-close-btn" aria-label="收合聊天視窗" onClick={onClose}><X size={18} /></button>
  </div>;
}
