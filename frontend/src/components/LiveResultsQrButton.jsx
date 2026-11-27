import { openLiveResultsFlyer } from "../meetingFlyer";

export default function LiveResultsQrButton({
  kind = "meeting",
  resourceId,
  className = "dashboard-btn",
  label = "Print live-results QR",
}) {
  if (!resourceId) return null;
  return (
    <button
      type="button"
      className={className}
      onClick={() => openLiveResultsFlyer(kind, resourceId)}
    >
      {label}
    </button>
  );
}
