import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function MeetingDetailsPage() {
  const { id } = useParams();
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState("");
  const [summaryBody, setSummaryBody] = useState("");
  const [summaryMsg, setSummaryMsg] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/meetings/${id}/`)
      .then((res) => {
        if (!cancelled) setMeeting(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not load meeting.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const wall = meeting?.wall;
  const phase = wall?.phase || "upcoming";

  const handleCreateSummary = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSummaryMsg("");
    try {
      const res = await api.post(`/api/meetings/${id}/summary/`, {
        body: summaryBody.trim(),
        status: wall?.is_organizer ? "published" : "submitted",
      });
      setSummaryMsg(
        res.data.status === "published"
          ? "Summary published."
          : "Minutes submitted for organizer review."
      );
      setSummaryBody("");
      const refreshed = await api.get(`/api/meetings/${id}/`);
      setMeeting(refreshed.data);
    } catch (err) {
      setSummaryMsg(err.response?.data?.detail || "Could not save summary.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/" className="dashboard-back">
          ← Home
        </Link>

        {error && <p className="dashboard-error">{error}</p>}
        {!meeting && !error && <p className="dashboard-empty">Loading…</p>}

        {meeting && (
          <div className="dashboard-card">
            <div className="dashboard-header">
              <h1>{meeting.title}</h1>
              <p>
                {meeting.organization_name}
                {meeting.wall?.phase
                  ? ` · ${meeting.wall.phase.replace("_", " ")}`
                  : ""}
              </p>
            </div>

            {meeting.description ? <p>{meeting.description}</p> : null}

            <dl className="meeting-details-list">
              {meeting.scheduled_start_at && (
                <>
                  <dt>Starts</dt>
                  <dd>{new Date(meeting.scheduled_start_at).toLocaleString()}</dd>
                </>
              )}
              {meeting.scheduled_end_at && (
                <>
                  <dt>Expected end</dt>
                  <dd>{new Date(meeting.scheduled_end_at).toLocaleString()}</dd>
                </>
              )}
              {meeting.location && (
                <>
                  <dt>Location</dt>
                  <dd>{meeting.location}</dd>
                </>
              )}
              {meeting.community_code && (
                <>
                  <dt>Community code</dt>
                  <dd>
                    <code>{meeting.community_code}</code>
                  </dd>
                </>
              )}
            </dl>

            <div className="dashboard-actions">
              {phase === "in_progress" && (
                <Link to={`/m/${id}`} className="dashboard-btn dashboard-btn--primary">
                  Join Meeting
                </Link>
              )}
              {meeting.can_view_results && (
                <Link to={`/m/${id}/results`} className="dashboard-btn">
                  View Results
                </Link>
              )}
              {meeting.published_summary && (
                <Link to={`/m/${id}/summary`} className="dashboard-btn">
                  Read Summary
                </Link>
              )}
            </div>

            {meeting.can_create_summary && (
              <form className="dashboard-form" onSubmit={handleCreateSummary}>
                <h2>
                  {wall?.is_organizer
                    ? "Create Minutes"
                    : "Submit Meeting Minutes"}
                </h2>
                <div className="dashboard-field">
                  <label htmlFor="summary-body">Summary</label>
                  <textarea
                    id="summary-body"
                    rows={8}
                    value={summaryBody}
                    onChange={(e) => setSummaryBody(e.target.value)}
                    required
                  />
                </div>
                {summaryMsg && <p className="dashboard-meta">{summaryMsg}</p>}
                <button
                  type="submit"
                  className="dashboard-btn dashboard-btn--primary"
                  disabled={saving}
                >
                  {saving
                    ? "Saving…"
                    : wall?.is_organizer
                      ? "Publish Summary"
                      : "Submit Minutes"}
                </button>
              </form>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
