/** Open printable meeting flyer in a new browser tab. */
export function meetingJoinUrl(meetingId) {
  const id = String(meetingId ?? "").trim();
  if (!id) return "";
  return `${window.location.origin}/m/${id}`;
}

export function meetingFlyerPath(meetingId) {
  const id = String(meetingId ?? "").trim();
  if (!id) return "";
  return `/m/${id}/flyer`;
}

export function openMeetingFlyer(meetingId) {
  const path = meetingFlyerPath(meetingId);
  if (!path) return;
  window.open(path, "_blank", "noopener,noreferrer");
}

/** kind: "meeting" (/m/:id) or "survey" (/s/:id). */
function resourcePrefix(kind) {
  return kind === "survey" ? "s" : "m";
}

export function resourceJoinUrl(kind, id) {
  const value = String(id ?? "").trim();
  if (!value) return "";
  return `${window.location.origin}/${resourcePrefix(kind)}/${value}`;
}

export function liveResultsPath(kind, id) {
  const value = String(id ?? "").trim();
  if (!value) return "";
  return `/${resourcePrefix(kind)}/${value}/live-results`;
}

export function liveResultsUrl(kind, id) {
  const path = liveResultsPath(kind, id);
  return path ? `${window.location.origin}${path}` : "";
}

export function openLiveResultsFlyer(kind, id) {
  const path = liveResultsPath(kind, id);
  if (!path) return;
  window.open(`${path}/flyer`, "_blank", "noopener,noreferrer");
}

export function qrCodeImageUrl(targetUrl, size = 400) {
  const data = encodeURIComponent(targetUrl || "");
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${data}`;
}
