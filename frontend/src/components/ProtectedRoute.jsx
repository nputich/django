import { jwtDecode } from "jwt-decode";
import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import api from "../api";
import { REFRESH_TOKEN, ACCESS_TOKEN } from "../constants";
import { clearAuth } from "../auth";

function ProtectedRoute({ children, skipProfileCheck = false }) {
  const [isAuthorized, setIsAuthorized] = useState(null);
  const [profileComplete, setProfileComplete] = useState(null);
  const location = useLocation();

  const loadProfileStatus = useCallback(async () => {
    if (skipProfileCheck || location.state?.profileComplete) {
      setProfileComplete(true);
      return;
    }
    try {
      const res = await api.get("/api/me/");
      setProfileComplete(Boolean(res.data.profile_complete));
    } catch {
      setProfileComplete(true);
    }
  }, [skipProfileCheck, location.state?.profileComplete]);

  useEffect(() => {
    let cancelled = false;

    const refreshToken = async () => {
      const refresh = localStorage.getItem(REFRESH_TOKEN);
      if (!refresh) {
        throw new Error("missing refresh token");
      }

      const res = await axios.post(
        `${import.meta.env.VITE_API_URL}/api/token/refresh/`,
        { refresh }
      );
      if (res.status !== 200) {
        throw new Error("refresh failed");
      }
      localStorage.setItem(ACCESS_TOKEN, res.data.access);
      if (!cancelled) {
        setIsAuthorized(true);
      }
    };

    const auth = async () => {
      const token = localStorage.getItem(ACCESS_TOKEN);
      if (!token) {
        if (!cancelled) {
          setIsAuthorized(false);
          setProfileComplete(true);
        }
        return;
      }

      try {
        const decoded = jwtDecode(token);
        const tokenExpiration = decoded.exp;
        const now = Date.now() / 1000;

        if (tokenExpiration < now) {
          await refreshToken();
        } else if (!cancelled) {
          setIsAuthorized(true);
        }

        if (!cancelled) {
          await loadProfileStatus();
        }
      } catch (error) {
        console.log(error);
        clearAuth();
        if (!cancelled) {
          setIsAuthorized(false);
          setProfileComplete(true);
        }
      }
    };

    auth();

    return () => {
      cancelled = true;
    };
  }, [loadProfileStatus]);

  useEffect(() => {
    if (isAuthorized !== true) {
      return;
    }
    loadProfileStatus();
  }, [isAuthorized, location.pathname, location.state?.profileComplete, loadProfileStatus]);

  if (isAuthorized === null || profileComplete === null) {
    return <div>Loading...</div>;
  }

  if (!isAuthorized) {
    return <Navigate to="/" replace />;
  }

  if (
    !skipProfileCheck &&
    !profileComplete &&
    location.pathname !== "/complete-profile"
  ) {
    return (
      <Navigate to="/complete-profile" state={{ from: location }} replace />
    );
  }

  return children;
}

export default ProtectedRoute;
