import { Link } from "react-router-dom";
import "../styles/Dashboard.css";

/**
 * Short upgrade prompt for locked Free-plan create actions.
 * Reassures that historical data remains available.
 */
export default function UpgradeRequiredModal({
  open,
  title,
  body,
  billingPath,
  onClose,
}) {
  if (!open) return null;
  return (
    <div className="upgrade-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="upgrade-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upgrade-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="upgrade-modal-title">{title}</h2>
        <p>{body}</p>
        <p className="upgrade-modal-reassure">
          Your previous meetings, surveys, responses, and reports remain available.
        </p>
        <div className="upgrade-modal-actions">
          <button type="button" className="dashboard-btn" onClick={onClose}>
            Not now
          </button>
          <Link to={billingPath} className="dashboard-btn dashboard-btn--primary">
            View plans
          </Link>
        </div>
      </div>
    </div>
  );
}
