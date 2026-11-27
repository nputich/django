/**
 * Capacitor injects window.Capacitor in the native WebView.
 * Keep this free of package imports so the website bundle stays lean.
 */
export function isNativeApp() {
  try {
    return (
      typeof window !== "undefined" &&
      window.Capacitor?.isNativePlatform?.() === true
    );
  } catch {
    return false;
  }
}

/**
 * True when the UI should show the local/dev chrome (gray nav banner).
 * Prefer build-time VITE_APP_ENV; also treat localhost as dev so local QA is obvious.
 * Capacitor WebViews use hostname "localhost" — never treat those as dev.
 */
export function isDevEnvironment() {
  if (isNativeApp()) {
    return false;
  }

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
