const STORAGE_KEY = "survey_response_session";

export function getSurveyResponseSession() {
  let session = localStorage.getItem(STORAGE_KEY);
  if (!session) {
    session = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, session);
  }
  return session;
}
