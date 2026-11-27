import { useState } from "react";

function ChevronDown({ className = "" }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export default function DashboardCollapsibleSection({
  id,
  title,
  children,
  defaultOpen = false,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = `${id}-panel`;

  return (
    <section
      className={`dashboard-card dashboard-collapsible${
        open ? " dashboard-collapsible--open" : ""
      }`}
    >
      <button
        type="button"
        id={id}
        className="dashboard-collapsible-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{title}</span>
        <ChevronDown className="dashboard-collapsible-chevron" />
      </button>
      <div id={panelId} className="dashboard-collapsible-panel" role="region" aria-labelledby={id}>
        <div className="dashboard-collapsible-panel-inner">{children}</div>
      </div>
    </section>
  );
}
