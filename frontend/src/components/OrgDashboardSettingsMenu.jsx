import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

/**
 * Compact menu for secondary org dashboard settings (board, etc.).
 * Sits next to Ownership & Organization in the action bar.
 */
export default function OrgDashboardSettingsMenu({ slug }) {
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
        aria-label="More organization settings"
        onClick={() => setOpen((v) => !v)}
      >
        ···
      </button>
      {open && (
        <div className="dashboard-action-menu-panel" role="menu">
          <Link
            role="menuitem"
            to={`/dashboard/${slug}/reports`}
            onClick={() => setOpen(false)}
          >
            Reports
          </Link>
          <Link
            role="menuitem"
            to={`/dashboard/${slug}/shared-with-us`}
            onClick={() => setOpen(false)}
          >
            Meetings shared with us
          </Link>
          <Link
            role="menuitem"
            to={`/dashboard/${slug}/board-settings`}
            onClick={() => setOpen(false)}
          >
            Board settings
          </Link>
          <Link
            role="menuitem"
            to={`/dashboard/${slug}/relationships`}
            onClick={() => setOpen(false)}
          >
            Relationships
          </Link>
          <Link
            role="menuitem"
            to={`/dashboard/${slug}/umbrella`}
            onClick={() => setOpen(false)}
          >
            Umbrella license &amp; usage
          </Link>
        </div>
      )}
    </div>
  );
}
