import { jwtDecode } from "jwt-decode";
import axios from "axios";
import { REFRESH_TOKEN, ACCESS_TOKEN } from "../constants";
import { clearAuth } from "../auth";
import { useState, useEffect } from "react";

function redirectHome() {
    clearAuth();
    window.location.replace("/");
}

function ProtectedRoute({ children }) {
    const [isAuthorized, setIsAuthorized] = useState(null);

    useEffect(() => {
        auth().catch(redirectHome);
    }, []);

    const refreshToken = async () => {
        const refresh = localStorage.getItem(REFRESH_TOKEN);
        if (!refresh) {
            redirectHome();
            return;
        }

        try {
            const res = await axios.post(
                `${import.meta.env.VITE_API_URL}/api/token/refresh/`,
                { refresh },
            );
            if (res.status === 200) {
                localStorage.setItem(ACCESS_TOKEN, res.data.access);
                setIsAuthorized(true);
            } else {
                redirectHome();
            }
        } catch (error) {
            console.log(error);
            redirectHome();
        }
    };

    const auth = async () => {
        const token = localStorage.getItem(ACCESS_TOKEN);
        if (!token) {
            setIsAuthorized(false);
            return;
        }

        try {
            const decoded = jwtDecode(token);
            const tokenExpiration = decoded.exp;
            const now = Date.now() / 1000;

            if (tokenExpiration < now) {
                await refreshToken();
            } else {
                setIsAuthorized(true);
            }
        } catch {
            redirectHome();
        }
    };

    if (isAuthorized === null) {
        return <div>Loading...</div>;
    }

    if (!isAuthorized) {
        redirectHome();
        return null;
    }

    return children;
}

export default ProtectedRoute;
