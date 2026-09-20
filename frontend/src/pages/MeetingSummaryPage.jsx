import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function MeetingSummaryPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/meetings/${id}/summary/`)
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail || "No published summary is available."
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/m/${id}/details`} className="dashboard-back">
          ← Meeting details
        </Link>

        {error && <p className="dashboard-error">{error}</p>}
        {!data && !error && <p className="dashboard-empty">Loading…</p>}

        {data && (
          <div className="dashboard-card">
            <div className="dashboard-header">
              <h1>{data.meeting_title}</h1>
              <p>Meeting summary</p>
            </div>
            {data.published_at && (
              <p className="dashboard-meta">
                Published {new Date(data.published_at).toLocaleString()}
              </p>
            )}
            <div className="meeting-summary-body">
              {data.body.split("\n").map((line, i) => (
                <p key={i}>{line || "\u00a0"}</p>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
