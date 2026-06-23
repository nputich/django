import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

export default function OrgHubPage() {
  const { slug } = useParams();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/hub/`)
      .then((res) => setOrg(res.data))
      .catch(() => setError("Organization not found."));
  }, [slug]);

  if (error) {
    return (
      <div className="resource-page">
        <p>{error}</p>
        <Link to="/">Back to home</Link>
      </div>
    );
  }

  if (!org) return <div className="resource-page">Loading...</div>;

  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>{org.name}</h1>
      {org.description && <p>{org.description}</p>}

      <section className="hub-section">
        <h2>Surveys</h2>
        {org.surveys.length === 0 ? (
          <p>No active surveys.</p>
        ) : (
          <ul className="hub-list">
            {org.surveys.map((s) => (
              <li key={s.id}>
                <Link to={`/s/${s.id}`}>{s.title}</Link>
                {s.description && <p>{s.description}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="hub-section">
        <h2>Meetings</h2>
        {org.meetings.length === 0 ? (
          <p>No upcoming meetings.</p>
        ) : (
          <ul className="hub-list">
            {org.meetings.map((m) => (
              <li key={m.id}>
                <Link to={`/m/${m.id}`}>{m.title}</Link>
                {m.description && <p>{m.description}</p>}
                <p className="resource-meta">
                  {m.status}
                  {m.scheduled_start_at &&
                    ` · ${new Date(m.scheduled_start_at).toLocaleString()}`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {org.has_board && (
        <section className="hub-section">
          <h2>Message board</h2>
          <Link to={`/org/${org.slug}/board`}>Go to message board</Link>
        </section>
      )}
    </div>
  );
}