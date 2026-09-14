import CustomerServiceFilled from "@ant-design/icons/CustomerServiceFilled";

export default function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark${compact ? " is-compact" : ""}`} aria-label="CRM Console">
      <span className="brand-mark__icon"><CustomerServiceFilled /></span>
      {!compact && <strong>CRM Console</strong>}
    </div>
  );
}
