import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

/**
 * Compact menu for secondary personal dashboard settings.
 */
export default function PersonalDashboardSettingsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="dashboard-action-menu" ref={ref}>
      <button
        type="button"
        className="dashboard-btn"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="More dashboard settings"
        onClick={() => setOpen((v) => !v)}
      >
        ···
      </button>
      {open && (
        <div className="dashboard-action-menu-panel" role="menu">
          <Link
            role="menuitem"
            to="/dashboard/board-settings"
            onClick={() => setOpen(false)}
          >
            Board settings
          </Link>
        </div>
      )}
    </div>
  );
}
