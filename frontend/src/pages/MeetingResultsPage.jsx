import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function MeetingResultsPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/meetings/${id}/community-results/`)
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail || "Meeting results are not available."
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
              <h1>{data.title}</h1>
              <p>Meeting results</p>
            </div>
            {data.totals && (
              <p className="dashboard-meta">
                {data.totals.participant_count} participants ·{" "}
                {data.totals.response_count} responses
              </p>
            )}
            {(data.slides || []).length === 0 ? (
              <p className="dashboard-empty">No slide results to show yet.</p>
            ) : (
              (data.slides || []).map((slide) => (
                <section key={slide.slide_id} className="meeting-results-slide">
                  <h2>{slide.title || `Slide ${slide.slide_id}`}</h2>
                  {(slide.bars || []).length === 0 ? (
                    <p className="dashboard-meta">No responses for this slide.</p>
                  ) : (
                    <ul className="meeting-results-bars">
                      {slide.bars.map((bar) => (
                        <li key={bar.label}>
                          <strong>{bar.label}</strong>
                          <span>
                            {bar.count}
                            {bar.percent != null ? ` (${bar.percent}%)` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}
