import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/Tags.css";

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString();
}

function SharedResults({ slug, meetingId, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/shared-meetings/${meetingId}/`)
      .then((res) => setData(res.data))
      .catch((err) => setError(err.response?.data?.detail || "Could not load results."));
  }, [slug, meetingId]);

  const download = async () => {
    try {
      const res = await api.get(`/api/organizations/${slug}/shared-meetings/${meetingId}/`, {
        params: { export: "csv" },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `shared-meeting-${meetingId}-${data?.access || "results"}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download.");
    }
  };

  if (error) return <p className="dashboard-error">{error}</p>;
  if (!data) return <p className="dashboard-meta">Loading…</p>;

  return (
    <div className="dashboard-card">
      <div className="dashboard-section-header">
        <div>
          <h2>{data.meeting.title}</h2>
          <p className="dashboard-meta">
            {data.meeting.organization.name} · {data.participant_count} participants ·{" "}
            <span className={`share-access share-access--${data.access}`}>
              {data.access === "full" ? "Full data" : "Buckets and totals"}
            </span>
          </p>
        </div>
        <div className="dashboard-actions">
          <button type="button" className="dashboard-btn dashboard-btn--primary" onClick={download}>
            Download CSV
          </button>
          <button type="button" className="dashboard-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
      {data.access !== "full" && (
        <p className="dashboard-meta">
          This share was granted after the meeting started or has since been revoked, so only
          combined totals are available. Individual answers are not included.
        </p>
      )}
      {data.slides.map((s) => (
        <div key={s.slide_id} className="report-question">
          <h3>{s.prompt}</h3>
          <p className="dashboard-meta">
            {s.response_count} responses · {s.participant_count} participants
          </p>
          {s.choice_counts && (
            <ul className="dashboard-list">
              {Object.entries(s.choice_counts).map(([label, n]) => (
                <li key={label}>
                  {label}: <strong>{n}</strong>
                </li>
              ))}
            </ul>
          )}
          {s.issue_counts && (
            <ul className="dashboard-list">
              {Object.entries(s.issue_counts).map(([label, n]) => (
                <li key={label}>
                  {label}: <strong>{n}</strong>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      {data.full_rows && (
        <p className="dashboard-meta">
          Full dataset: {data.full_rows.length} rows, keyed by anonymous participant ID. Use
          Download CSV to open in Excel.
        </p>
      )}
    </div>
  );
}

export default function OrgSharedMeetingsPage() {
  const { slug } = useParams();
  const [items, setItems] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/shared-meetings/`)
      .then((res) => setItems(res.data.shared))
      .catch((err) => setError(err.response?.data?.detail || "Could not load shared meetings."));
  }, [slug]);

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {slug}
        </Link>
        <div className="dashboard-header">
          <h1>Meetings shared with us</h1>
          <p>
            Results other organizations chose to share with you. Full data is only available when
            the organizer declared the share to participants before the meeting began.
          </p>
        </div>
        {error && <p className="dashboard-error">{error}</p>}
        {openId && <SharedResults slug={slug} meetingId={openId} onClose={() => setOpenId(null)} />}
        <div className="dashboard-card">
          {items.length === 0 ? (
            <p className="dashboard-empty">Nothing has been shared with your organization yet.</p>
          ) : (
            <ul className="share-list dashboard-list">
              {items.map((s) => (
                <li key={s.id}>
                  <div>
                    <strong>{s.meeting.title}</strong>
                    <p className="dashboard-meta">
                      {s.meeting.organization.name} · {s.meeting.status} ·{" "}
                      {formatDate(s.meeting.started_at || s.meeting.scheduled_start_at)} ·{" "}
                      <span className={`share-access share-access--${s.effective_access}`}>
                        {s.effective_access_label}
                      </span>
                      {s.status === "revoked" && " · sharing ended"}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => setOpenId(openId === s.meeting.id ? null : s.meeting.id)}
                  >
                    {openId === s.meeting.id ? "Hide" : "View results"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
