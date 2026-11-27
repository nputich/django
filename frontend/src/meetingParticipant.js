const STORAGE_PREFIX = "communib_meeting_";

export function getMeetingParticipant(meetingId) {
  const raw = localStorage.getItem(`${STORAGE_PREFIX}${meetingId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveMeetingParticipant(meetingId, data) {
  localStorage.setItem(`${STORAGE_PREFIX}${meetingId}`, JSON.stringify(data));
}

export function clearMeetingParticipant(meetingId) {
  localStorage.removeItem(`${STORAGE_PREFIX}${meetingId}`);
}
