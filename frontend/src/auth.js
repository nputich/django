import { jwtDecode } from "jwt-decode";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "./constants";

const AUTH_API_BASE = "communib_auth_api_base";

function currentApiBase() {
  return String(import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
}

export function clearAuth() {
  localStorage.removeItem(ACCESS_TOKEN);
  localStorage.removeItem(REFRESH_TOKEN);
  localStorage.removeItem(AUTH_API_BASE);
}

/** Persist tokens and bind them to the API that issued them. */
export function setAuthTokens(access, refresh) {
  localStorage.setItem(ACCESS_TOKEN, access);
  if (refresh) {
    localStorage.setItem(REFRESH_TOKEN, refresh);
  }
  localStorage.setItem(AUTH_API_BASE, currentApiBase());
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN);
}

function tokensMatchCurrentApi() {
  const saved = localStorage.getItem(AUTH_API_BASE);
  const current = currentApiBase();
  if (!saved) {
    // Older sessions weren't bound to an API host. Force a fresh login on local
    // so production tokens aren't reused against localhost.
    if (current.includes("localhost") || current.includes("127.0.0.1")) {
      return false;
    }
    return true;
  }
  return saved === current;
}

export function isAccessTokenValid() {
  if (!tokensMatchCurrentApi()) {
    clearAuth();
    return false;
  }
  const token = getAccessToken();
  if (!token) return false;
  try {
    const { exp } = jwtDecode(token);
    return exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

/** Clear expired / wrong-environment tokens; returns true if session is usable. */
export function ensureValidSession() {
  if (!tokensMatchCurrentApi()) {
    clearAuth();
    return false;
  }
  const token = getAccessToken();
  if (!token) return false;
  if (isAccessTokenValid()) return true;
  clearAuth();
  return false;
}
