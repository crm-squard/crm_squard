import { Package, Truck, CheckCircle2, Clock, type LucideIcon } from "lucide-react";

interface OrderStage {
  key: string;
  label: string;
  icon: LucideIcon;
}

interface OrderCardProps {
  code: string;
  status: number;
  eta: string;
  items: string;
}

const ORDER_STAGES: OrderStage[] = [
  { key: "placed", label: "已下單", icon: Clock },
  { key: "shipped", label: "備貨出貨", icon: Package },
  { key: "delivering", label: "配送中", icon: Truck },
  { key: "done", label: "已送達", icon: CheckCircle2 },
];

export default function OrderCard({ code, status, eta, items }: OrderCardProps) {
  return (
    <div className="ccw-row ccw-row-bot">
      <div className="ccw-order-card">
        <div className="ccw-order-head">
          <span className="ccw-order-code">訂單 #{code}</span>
          <span className="ccw-order-eta">預計 {eta} 送達</span>
        </div>
        <p className="ccw-order-items">{items}</p>
        <div className="ccw-timeline">
          {ORDER_STAGES.map((stage, stageIndex) => {
            const Icon = stage.icon;
            const state = stageIndex < status ? "done" : stageIndex === status ? "active" : "pending";
            return (
              <div className="ccw-timeline-step" key={stage.key}>
                <div className={`ccw-timeline-node ccw-node-${state}`}>
                  <Icon size={14} strokeWidth={2.4} />
                </div>
                <span className={`ccw-timeline-label ccw-label-${state}`}>{stage.label}</span>
                {stageIndex < ORDER_STAGES.length - 1 && (
                  <div className={`ccw-timeline-bar ${stageIndex < status ? "ccw-bar-done" : ""}`} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
