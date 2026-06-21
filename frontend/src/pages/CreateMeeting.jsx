import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import { normalizeAccessCode } from "../accessCode";
import "../styles/Dashboard.css";

export default function CreateMeeting() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [accessMode, setAccessMode] = useState("public");
  const [accessCode, setAccessCode] = useState("");
  const [codeStatus, setCodeStatus] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const checkCode = useCallback(async (code) => {
    if (!code.trim()) {
      setCodeStatus(null);
      return;
    }
    try {
      const res = await api.get("/api/access-codes/check/", {
        params: { code: code.trim(), type: "meeting" },
      });
      setCodeStatus(res.data);
    } catch (err) {
      setCodeStatus({
        available: false,
        detail: err.response?.data?.detail || "Could not check code.",
      });
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess(null);
    setSubmitting(true);

    try {
      const res = await api.post(`/api/organizations/${slug}/meetings/`, {
        title: title.trim(),
        description: description.trim(),
        access_mode: accessMode,
        access_code: accessCode.trim(),
      });
      setSuccess(res.data);
      setTimeout(() => navigate(`/dashboard/${slug}`), 2500);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          JSON.stringify(err.response?.data) ||
          "Could not create meeting."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {slug}
        </Link>
        <div className="dashboard-header">
          <h1>Create meeting</h1>
          <p>Schedule a meeting and assign an access code for public search.</p>
        </div>

        {success && (
          <div className="dashboard-success">
            <strong>Meeting created!</strong>
            <p>
              Access code:{" "}
              <span className="dashboard-code">{success.access_code.code}</span>
            </p>
            <p>Redirecting to dashboard...</p>
          </div>
        )}

        <form className="dashboard-form" onSubmit={handleSubmit}>
          <div className="dashboard-field">
            <label htmlFor="meeting-title">Title</label>
            <input
              id="meeting-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="meeting-description">Description</label>
            <textarea
              id="meeting-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="meeting-access">Access mode</label>
            <select
              id="meeting-access"
              value={accessMode}
              onChange={(e) => setAccessMode(e.target.value)}
            >
              <option value="public">Public</option>
              <option value="semi_public">Semi-public (login required)</option>
              <option value="private">Private</option>
            </select>
          </div>

          <div className="dashboard-field">
            <label htmlFor="meeting-code">Access code (optional)</label>
            <input
              id="meeting-code"
              value={accessCode}
              onChange={(e) => {
                setAccessCode(normalizeAccessCode(e.target.value));
                setCodeStatus(null);
              }}
              onBlur={() => checkCode(accessCode)}
              placeholder="Leave blank to auto-generate"
            />
            <small>
              3–32 characters, uppercase letters, numbers, and hyphens. Must not be in
              use by an active meeting.
            </small>
            {codeStatus && (
              <p
                className={`dashboard-code-status ${
                  codeStatus.available
                    ? "dashboard-code-status--ok"
                    : "dashboard-code-status--bad"
                }`}
              >
                {codeStatus.available
                  ? `Available${codeStatus.normalized ? `: ${codeStatus.normalized}` : ""}`
                  : codeStatus.detail || "Not available"}
              </p>
            )}
          </div>

          {error && <p className="dashboard-error">{error}</p>}

          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create meeting"}
          </button>
        </form>
      </main>
    </div>
  );
}
