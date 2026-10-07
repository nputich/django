import { openMeetingFlyer } from "../meetingFlyer";

export default function MeetingFlyerButton({
  meetingId,
  className = "dashboard-btn",
  label = "Print / share flyer",
}) {
  if (!meetingId) return null;
  return (
    <button
      type="button"
      className={className}
      onClick={() => openMeetingFlyer(meetingId)}
    >
      {label}
    </button>
  );
}
