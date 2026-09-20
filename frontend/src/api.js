import axios from "axios";
import { ACCESS_TOKEN } from "./constants";
import { clearAuth } from "./auth";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = String(error.config?.url || "");
    const detail = error.response?.data?.detail;
    const isAuthAttempt =
      url.includes("/api/token/") || url.includes("/api/user/register/");
    const tokenInvalid =
      status === 401 &&
      typeof detail === "string" &&
      detail.toLowerCase().includes("token");
    if ((status === 401 || tokenInvalid) && !isAuthAttempt) {
      clearAuth();
    }
    return Promise.reject(error);
  },
);

export default api;
