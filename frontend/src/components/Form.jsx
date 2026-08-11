import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";
import "../styles/Form.css";
import LoadingIndicator from "./LoadingIndicator";

function Form({ route, method, compact = false, header = false, hideFooter = false }) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const location = useLocation();
    const name = method === "login" ? "Login" : "Register";

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const res = await api.post(route, { username, password });
            const redirectTo = () => {
                const from = location.state?.from;
                if (from && typeof from.pathname === "string") {
                    return `${from.pathname}${from.search || ""}`;
                }
                return "/dashboard";
            };
            if (method === "login") {
                localStorage.setItem(ACCESS_TOKEN, res.data.access);
                localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
                const next = redirectTo();
                window.location.href = next.startsWith("/") ? next : "/dashboard";
            } else {
                // Auto sign-in after register so "create organization" return works.
                const tokenRes = await api.post("/api/token/", {
                    username,
                    password,
                });
                localStorage.setItem(ACCESS_TOKEN, tokenRes.data.access);
                localStorage.setItem(REFRESH_TOKEN, tokenRes.data.refresh);
                const next = redirectTo();
                window.location.href = next.startsWith("/") ? next : "/dashboard";
            }
        } catch (error) {
            alert(error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <form
            onSubmit={handleSubmit}
            className={[
                "form-container",
                compact ? "form-container--compact" : "",
                header ? "form-container--header-login" : "",
            ]
                .filter(Boolean)
                .join(" ")}
        >
            {!compact && !header && <h1>{name}</h1>}
            {header && method === "login" && (
                <div className="form-header-login-title">Login</div>
            )}
            <div className={compact ? "form-fields" : undefined}>
            <input
                className="form-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                required
            />
            <input
                className="form-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
            />
            {loading && <LoadingIndicator />}
            <button className="form-button" type="submit" disabled={loading}>
                {method === "login" ? "Sign in" : name}
            </button>
            </div>
            {!hideFooter && (
                <p className={`form-footer${compact ? " form-footer--compact" : ""}`}>
                    {method === "login" ? (
                        <>
                            New here?{" "}
                            <Link to="/register" state={location.state}>
                                Register
                            </Link>
                        </>
                    ) : (
                        <>
                            Already have an account?{" "}
                            <Link to="/" state={location.state}>
                                Sign in
                            </Link>
                        </>
                    )}
                </p>
            )}
        </form>
    );
}

export default Form;