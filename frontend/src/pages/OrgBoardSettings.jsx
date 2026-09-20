import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function OrgBoardSettings() {
  const { slug } = useParams();
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState("public");
  const [hubPreviewCount, setHubPreviewCount] = useState(5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [orgName, setOrgName] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return Promise.all([
      api.get(`/api/organizations/${slug}/dashboard/`),
      api.get(`/api/organizations/${slug}/board/`),
    ])
      .then(([dashRes, boardRes]) => {
        setOrgName(dashRes.data.name || slug);
        const board = boardRes.data.board || dashRes.data.board || {};
        setTitle(board.title || "");
        setMode(board.posting_mode || "public");
        setHubPreviewCount(
          typeof board.hub_preview_count === "number"
            ? board.hub_preview_count
            : 5
        );
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail || "Could not load board settings."
        );
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.patch(`/api/organizations/${slug}/board/settings/`, {
        title: title.trim(),
        posting_mode: mode,
        hub_preview_count: Number(hubPreviewCount),
      });
      setMessage("Board settings saved.");
      await load();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.title?.[0] ||
          err.response?.data?.hub_preview_count?.[0] ||
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
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {orgName || slug}
        </Link>
        <div className="dashboard-header">
          <h1>Board settings</h1>
          <p>Control who can post on your organization&apos;s board.</p>
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
                placeholder={orgName || "Organization name"}
              />
              <small className="dashboard-meta">
                Leave blank to show the organization name on the wall.
              </small>
            </div>
            <div className="dashboard-field">
              <label htmlFor="board-mode">Who can post</label>
              <select
                id="board-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="public">Everyone (logged in)</option>
                <option value="members_only">Members only</option>
                <option value="restricted">Restricted (admins only)</option>
              </select>
            </div>
            <div className="dashboard-field">
              <label htmlFor="hub-preview-count">
                Posts shown on organization hub
              </label>
              <input
                id="hub-preview-count"
                type="number"
                min={0}
                max={25}
                value={hubPreviewCount}
                onChange={(e) => setHubPreviewCount(e.target.value)}
              />
              <small className="dashboard-meta">
                Newest posts appear on the public hub page. Use 0 to hide the
                board preview there.
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
