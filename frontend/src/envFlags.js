/**
 * True when the UI should show the local/dev chrome (gray nav banner).
 * Prefer build-time VITE_APP_ENV; also treat localhost as dev so local QA is obvious.
 */
export function isDevEnvironment() {
  const env = String(import.meta.env.VITE_APP_ENV || "")
    .trim()
    .toLowerCase();
  if (env === "local" || env === "development" || env === "dev") {
    return true;
  }
  if (env === "production" || env === "prod") {
    return false;
  }

  if (typeof window === "undefined") {
    return false;
  }

  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1" || host === "0.0.0.0";
}
