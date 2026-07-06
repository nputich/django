import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function OrgDashboard() {
  const { slug } = useParams();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [startingId, setStartingId] = useState(null);

  const loadDashboard = () => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/dashboard/`)
      .then((res) => setOrg(res.data))
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not load this organization dashboard."
        );
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDashboard();
  }, [slug]);

  const handleStartMeeting = async (meetingId) => {
    setStartingId(meetingId);
    try {
      await api.post(`/api/organizations/${slug}/meetings/${meetingId}/start/`);
      await loadDashboard();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not start meeting.");
    } finally {
      setStartingId(null);
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← All organizations
        </Link>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {org && (
          <>
            <div className="dashboard-header">
              <h1>{org.name}</h1>
              <p>{org.description || "Organization dashboard"}</p>
            </div>

            <div className="dashboard-actions">
              <Link
                to={`/dashboard/${slug}/surveys/new`}
                className="dashboard-btn dashboard-btn--primary"
              >
                Create survey
              </Link>
              <Link
                to={`/dashboard/${slug}/meetings/new`}
                className="dashboard-btn dashboard-btn--primary"
              >
                Create meeting
              </Link>
              <Link
                to={`/org/${slug}/hub`}
                className="dashboard-btn"
                target="_blank"
                rel="noopener noreferrer"
              >
                View public hub
              </Link>
            </div>

            <div className="dashboard-card">
              <h2>Surveys</h2>
              {org.surveys.length === 0 ? (
                <p className="dashboard-empty">No surveys yet.</p>
              ) : (
                <ul className="dashboard-list">
                  {org.surveys.map((survey) => (
                    <li key={survey.id} className="dashboard-list-item">
                      <div>
                        <h3>{survey.title}</h3>
                        <p className="dashboard-meta">
                          {survey.is_active ? "Active" : "Inactive"} ·{" "}
                          <Link to={`/s/${survey.id}`}>Open survey</Link> ·{" "}
                          <Link to={`/dashboard/${slug}/surveys/${survey.id}/edit`}>
                            Edit
                          </Link>
                        </p>
                      </div>
                      <div>
                        {(survey.access_codes ?? []).map((code) => (
                          <span key={code.id} className="dashboard-code">
                            {code.code}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="dashboard-card">
              <h2>Meetings</h2>
              {org.meetings.length === 0 ? (
                <p className="dashboard-empty">No meetings yet.</p>
              ) : (
                <ul className="dashboard-list">
                  {org.meetings.map((meeting) => (
                    <li key={meeting.id} className="dashboard-list-item">
                      <div>
                        <h3>{meeting.title}</h3>
                        <p className="dashboard-meta">
                          {meeting.access_mode} · {meeting.status} ·{" "}
                          <Link to={`/m/${meeting.id}`}>Open meeting</Link> ·{" "}
                          <Link to={`/dashboard/${slug}/meetings/${meeting.id}/edit`}>
                            Edit
                          </Link>
                        </p>
                        {meeting.status === "scheduled" && (
                          <button
                            type="button"
                            className="dashboard-btn dashboard-btn--primary"
                            style={{ marginTop: "0.5rem" }}
                            disabled={startingId === meeting.id}
                            onClick={() => handleStartMeeting(meeting.id)}
                          >
                            {startingId === meeting.id ? "Starting..." : "Start meeting"}
                          </button>
                        )}
                        <Link
                          to={`/dashboard/${slug}/meetings/${meeting.id}/host`}
                          className="dashboard-btn"
                          style={{ marginTop: "0.5rem", display: "inline-flex" }}
                        >
                          Host controls
                        </Link>
                      </div>
                      <div>
                        {(meeting.access_codes ?? []).map((code) => (
                          <span key={code.id} className="dashboard-code">
                            {code.code}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
