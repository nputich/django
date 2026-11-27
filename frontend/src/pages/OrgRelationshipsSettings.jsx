import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/OrgLifecycle.css";
import "../styles/Relationships.css";

const STATUS_LABEL = {
  pending: "Pending",
  accepted: "Active",
  declined: "Declined",
  ended: "Ended",
  expired: "Expired",
};

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString();
}

export default function OrgRelationshipsSettings() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  // New request form
  const [direction, setDirection] = useState("child_of");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [target, setTarget] = useState(null);
  const [note, setNote] = useState("");
  const [isPublic, setIsPublic] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/relationships/`)
      .then((res) => setData(res.data))
      .catch((err) =>
        setError(err.response?.data?.detail || "Could not load relationships.")
      )
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (target || query.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .get("/api/organizations/lookup/", {
          params: { q: query.trim(), exclude: slug },
        })
        .then((res) => setResults(res.data.results || []))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [query, slug, target]);

  const runAction = async (fn, successText) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      if (successText) setMessage(successText);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "That action could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!target) {
      setError("Choose an organization from the search results.");
      return;
    }
    runAction(
      () =>
        api.post(`/api/organizations/${slug}/relationships/`, {
          target_slug: target.slug,
          direction,
          note,
          public: isPublic,
        }),
      `Request sent to ${target.name}. They will see it in their organization inbox.`
    ).then(() => {
      setTarget(null);
      setQuery("");
      setNote("");
    });
  };

  const action = (rel, verb) =>
    runAction(
      () => api.post(`/api/organizations/${slug}/relationships/${rel.id}/${verb}/`),
      verb === "accept"
        ? "Relationship accepted."
        : verb === "decline"
          ? "Request declined."
          : verb === "withdraw"
            ? "Request withdrawn."
            : "Relationship ended."
    );

  const togglePublic = (rel) =>
    runAction(
      () =>
        api.patch(`/api/organizations/${slug}/relationships/${rel.id}/`, {
          public: !rel.public,
        }),
      null
    );

  const orgName = data?.organization?.name || slug;

  const renderRow = (rel, { showRespond, showWithdraw, showEnd, showPublic }) => (
    <li key={rel.id} className="dashboard-card relationships-row">
      <div className="relationships-row-main">
        <strong>{rel.description}</strong>
        <p className="dashboard-meta">
          {rel.kind_label} · {STATUS_LABEL[rel.status] || rel.status}
          {rel.status === "pending" && rel.expires_at && ` · expires ${formatDate(rel.expires_at)}`}
          {rel.status === "accepted" && rel.responded_at && ` · since ${formatDate(rel.responded_at)}`}
          {" · "}
          <Link to={`/org/${rel.other_organization.slug}`}>View hub</Link>
          {rel.conversation_id && (
            <>
              {" · "}
              <Link to={`/dashboard/${slug}/inbox`}>Open thread</Link>
            </>
          )}
        </p>
        {rel.note && <p className="dashboard-meta">“{rel.note}”</p>}
      </div>
      <div className="inbox-actions">
        {showPublic && (
          <label className="relationships-public-toggle">
            <input
              type="checkbox"
              checked={rel.public}
              disabled={busy}
              onChange={() => togglePublic(rel)}
            />
            Show on hub
          </label>
        )}
        {showRespond && rel.can_respond && (
          <>
            <button
              type="button"
              className="dashboard-btn dashboard-btn--primary"
              disabled={busy}
              onClick={() => action(rel, "accept")}
            >
              Accept
            </button>
            <button
              type="button"
              className="dashboard-btn"
              disabled={busy}
              onClick={() => {
                if (window.confirm("Decline this request?")) action(rel, "decline");
              }}
            >
              Decline
            </button>
          </>
        )}
        {showWithdraw && rel.can_withdraw && (
          <button
            type="button"
            className="dashboard-btn"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Withdraw this request?")) action(rel, "withdraw");
            }}
          >
            Withdraw
          </button>
        )}
        {showEnd && rel.can_end && (
          <button
            type="button"
            className="dashboard-btn dashboard-btn--danger"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  `End the relationship with ${rel.other_organization.name}? They will be notified.`
                )
              ) {
                action(rel, "end");
              }
            }}
          >
            End
          </button>
        )}
      </div>
    </li>
  );

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {orgName}
        </Link>
        <div className="dashboard-header">
          <h1>Relationships</h1>
          <p>
            Link {orgName} to parent organizations, chapters, partners, and sponsors.
            The other organization must accept from its inbox. Relationships appear on
            hubs and make sharing results easier, but never grant admin access or data
            access on their own.
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading…</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {!loading && data && (
          <>
            <form className="dashboard-form dashboard-card" onSubmit={handleSubmit}>
              <h2>Request a relationship</h2>
              <div className="dashboard-field">
                <label htmlFor="rel-direction">{orgName} is…</label>
                <select
                  id="rel-direction"
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  disabled={busy}
                >
                  {data.directions.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="dashboard-field">
                <label htmlFor="rel-target">Organization</label>
                {target ? (
                  <div className="relationships-target">
                    <strong>{target.name}</strong>
                    <button
                      type="button"
                      className="dashboard-btn"
                      onClick={() => {
                        setTarget(null);
                        setQuery("");
                      }}
                    >
                      Change
                    </button>
                  </div>
                ) : (
                  <input
                    id="rel-target"
                    type="text"
                    value={query}
                    placeholder="Start typing an organization name…"
                    onChange={(e) => setQuery(e.target.value)}
                    disabled={busy}
                    autoComplete="off"
                  />
                )}
                {!target && results.length > 0 && (
                  <ul className="relationships-results">
                    {results.map((o) => (
                      <li key={o.slug}>
                        <button type="button" onClick={() => setTarget(o)}>
                          {o.name} <span className="dashboard-meta">/{o.slug}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="dashboard-field">
                <label htmlFor="rel-note">Message (optional)</label>
                <textarea
                  id="rel-note"
                  value={note}
                  maxLength={500}
                  rows={3}
                  onChange={(e) => setNote(e.target.value)}
                  disabled={busy}
                />
              </div>
              <label className="relationships-public-toggle">
                <input
                  type="checkbox"
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                  disabled={busy}
                />
                Show this relationship on both organizations&apos; public hubs
              </label>
              <button
                type="submit"
                className="dashboard-btn dashboard-btn--primary"
                disabled={busy || !target}
              >
                Send request
              </button>
            </form>

            {data.incoming_pending.length > 0 && (
              <section className="dashboard-section">
                <h2>Requests waiting for you</h2>
                <ul className="dashboard-list">
                  {data.incoming_pending.map((rel) =>
                    renderRow(rel, { showRespond: true })
                  )}
                </ul>
              </section>
            )}

            {data.outgoing_pending.length > 0 && (
              <section className="dashboard-section">
                <h2>Requests you sent</h2>
                <ul className="dashboard-list">
                  {data.outgoing_pending.map((rel) =>
                    renderRow(rel, { showWithdraw: true })
                  )}
                </ul>
              </section>
            )}

            <section className="dashboard-section">
              <h2>Active relationships</h2>
              {data.active.length === 0 ? (
                <p className="dashboard-empty">No active relationships yet.</p>
              ) : (
                <ul className="dashboard-list">
                  {data.active.map((rel) =>
                    renderRow(rel, { showEnd: true, showPublic: true })
                  )}
                </ul>
              )}
            </section>

            {data.history.length > 0 && (
              <section className="dashboard-section">
                <h2>History</h2>
                <ul className="dashboard-list">
                  {data.history.map((rel) => renderRow(rel, {}))}
                </ul>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
