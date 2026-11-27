import { useEffect, useState } from "react";
import api from "../api";

export default function PluginAccessQueue({ slug }) {
  const [requests, setRequests] = useState(null);
  const [comments, setComments] = useState({});
  const [error, setError] = useState("");
  const base = slug
    ? `/api/organizations/${slug}/plugins/access-requests/`
    : "/api/me/plugins/access-requests/";

  const load = () => {
    api
      .get(base)
      .then((res) => setRequests(res.data.requests ?? []))
      .catch((err) => {
        if (err.response?.status === 403) setRequests(null);
        else setError(err.response?.data?.detail || "Could not load access requests.");
      });
  };

  useEffect(() => {
    load();
  }, [slug]);

  const decide = async (id, decision) => {
    setError("");
    try {
      await api.post(`${base}${id}/`, {
        decision,
        comment: comments[id] || "",
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save that decision.");
    }
  };

  if (requests === null) return null;

  const pending = requests.filter((item) => item.status === "pending");

  return (
    <section className="dashboard-card">
      <h2>Access approval</h2>
      <p>Requests for plugins that need Communibetter approval.</p>
      {error && <p className="dashboard-error">{error}</p>}
      {pending.length === 0 && <p className="dashboard-empty">No requests waiting.</p>}
      {pending.map((item) => (
        <div key={item.id} className="dashboard-card">
          <p>
            <strong>{item.plugin_name}</strong> · {item.owner_kind} · {item.owner_label}
          </p>
          <p>Request: {item.request_comment || "No comment."}</p>
          <textarea
            rows={2}
            placeholder="Comment for the requester"
            value={comments[item.id] || ""}
            onChange={(event) =>
              setComments((current) => ({ ...current, [item.id]: event.target.value }))
            }
          />
          <div className="dashboard-actions">
            <button type="button" className="dashboard-btn dashboard-btn--blue" onClick={() => decide(item.id, "approve")}>
              Approve
            </button>
            <button type="button" className="dashboard-btn" onClick={() => decide(item.id, "deny")}>
              Deny
            </button>
          </div>
        </div>
      ))}
    </section>
  );
}
