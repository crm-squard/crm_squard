import { Sparkles, X } from "lucide-react";

interface ChatHeaderProps {
  brandName: string;
  logoUrl: string | null;
  onClose: () => void;
}

export default function ChatHeader({ brandName, logoUrl, onClose }: ChatHeaderProps) {
  return <div className="ccw-header">
    <div className="ccw-header-brand"><div className="ccw-header-icon">
      {logoUrl ? <img className="ccw-header-logo" src={logoUrl} alt="" /> : <Sparkles size={17} />}
    </div>
      <div><div className="ccw-header-title">{brandName}</div>
        <div className="ccw-header-status"><span className="ccw-status-dot" />線上服務中</div>
      </div>
    </div>
    <button className="ccw-close-btn" aria-label="收合聊天視窗" onClick={onClose}><X size={18} /></button>
  </div>;
}
