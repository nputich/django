import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function PersonalBoardSettings() {
  const [title, setTitle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return Promise.all([api.get("/api/me/"), api.get("/api/me/board/")])
      .then(([meRes, boardRes]) => {
        setDisplayName(
          meRes.data.display_name || meRes.data.username || "Your board"
        );
        setTitle(boardRes.data.title || "");
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail || "Could not load board settings."
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.patch("/api/me/board/settings/", { title: title.trim() });
      setMessage("Board settings saved.");
      await load();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.title?.[0] ||
          "Could not save board settings."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← Back to dashboard
        </Link>
        <div className="dashboard-header">
          <h1>Board settings</h1>
          <p>
            Your personal wall is private — only you can view and post here.
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading…</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {!loading && (
          <form className="dashboard-form dashboard-card" onSubmit={handleSave}>
            <div className="dashboard-field">
              <label htmlFor="board-title">Board title (optional)</label>
              <input
                id="board-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={displayName}
              />
              <small className="dashboard-meta">
                Leave blank to use your display name on the wall.
              </small>
            </div>
            <button
              type="submit"
              className="dashboard-btn dashboard-btn--primary"
              disabled={saving}
            >
              {saving ? "Saving…" : "Save board settings"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
