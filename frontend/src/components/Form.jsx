import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";
import "../styles/Form.css";
import LoadingIndicator from "./LoadingIndicator";

function Form({ route, method, compact = false }) {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const name = method === "login" ? "Login" : "Register";

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const res = await api.post(route, { username, password });
            if (method === "login") {
                localStorage.setItem(ACCESS_TOKEN, res.data.access);
                localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
                window.location.href = "/";
            } else {
                navigate("/");
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
            className={`form-container${compact ? " form-container--compact" : ""}`}
        >
            {!compact && <h1>{name}</h1>}
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
                {compact && method === "login" ? "Sign in" : name}
            </button>
            </div>
            <p className={`form-footer${compact ? " form-footer--compact" : ""}`}>
                {method === "login" ? (
                    <>
                        New here? <Link to="/register">Register</Link>
                    </>
                ) : (
                    <>
                        Already have an account? <Link to="/">Sign in</Link>
                    </>
                )}
            </p>
        </form>
    );
}

export default Form;