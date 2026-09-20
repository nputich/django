import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/Billing.css";
import "../styles/OrgLifecycle.css";
import "../styles/Relationships.css";

function fmtDate(value) {
  return value ? new Date(value).toLocaleDateString() : "";
}

function meter(m) {
  if (!m) return "0";
  return m.limit == null ? `${m.used} used` : `${m.used} of ${Number(m.limit).toLocaleString()}`;
}

export default function OrgUmbrellaPortal() {
  const { slug } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/billing/umbrella/`)
      .then((res) => setData(res.data))
      .catch((err) =>
        setError(err.response?.data?.detail || "Could not load the umbrella license portal.")
      )
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (fn, okText) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await fn();
      if (res?.data?.license !== undefined) setData(res.data);
      else await load();
      if (okText) setMessage(okText);
    } catch (err) {
      setError(err.response?.data?.detail || "That action could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const base = `/api/organizations/${slug}/billing/umbrella/`;
  const createLicense = () => run(() => api.post(base), "Umbrella license created.");
  const rotate = () =>
    run(() => api.post(`${base}rotate/`), "New code issued. The old code no longer works.");
  const setActive = (isActive) =>
    run(
      () => api.post(`${base}active/`, { is_active: isActive }),
      isActive ? "Code re-enabled." : "Code paused. Existing members keep coverage."
    );
  const removeMember = (m) => {
    if (
      !window.confirm(
        `Remove ${m.organization.name} from your umbrella license? They will drop to the free plan immediately and be notified.`
      )
    ) {
      return;
    }
    run(
      () => api.post(`${base}members/${m.relationship_id}/remove/`),
      `${m.organization.name} removed.`
    );
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(data.license.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable; user can select the text */
    }
  };

  const orgName = data?.organization?.name || slug;
  const license = data?.license;
  const pooled = data?.pooled_usage;

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main billing-page">
        <Link to={`/dashboard/${slug}/billing`} className="dashboard-back">
          ← Back to Billing &amp; Service
        </Link>
        <div className="dashboard-header">
          <h1>Umbrella license</h1>
          <p className="billing-org-name">{orgName}</p>
        </div>

        {loading && <p className="dashboard-empty">Loading…</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {!loading && data && (
          <>
            {data.is_member_elsewhere && (
              <p className="dashboard-error">
                This organization is covered by another organization&apos;s umbrella license
                and cannot issue its own.
              </p>
            )}

            {!license && !data.is_member_elsewhere && (
              <section className="billing-current">
                <h2 className="billing-section-title">Share your plan</h2>
                <div className="billing-current-card">
                  {data.can_offer ? (
                    <>
                      <p className="billing-current-status">
                        Create a code that chapters and member organizations can enter on
                        their Billing page. They will run on your{" "}
                        {data.backing_service_level_label} plan, and everything they use
                        counts against your pooled limits. You can see each member&apos;s
                        usage here, remove members, or rotate the code at any time.
                      </p>
                      <button
                        type="button"
                        className="dashboard-btn dashboard-btn--primary"
                        disabled={busy}
                        onClick={createLicense}
                      >
                        Create umbrella license
                      </button>
                    </>
                  ) : (
                    <p className="billing-current-status">
                      An umbrella license requires an active paid plan.{" "}
                      <Link to={`/dashboard/${slug}/billing`}>Choose a plan</Link> first.
                    </p>
                  )}
                </div>
              </section>
            )}

            {license && (
              <>
                <section className="billing-current">
                  <h2 className="billing-section-title">Your code</h2>
                  <div className="billing-current-card">
                    <p className="umbrella-code">
                      <code>{license.code}</code>
                      <button
                        type="button"
                        className="dashboard-btn"
                        onClick={copyCode}
                        disabled={busy}
                      >
                        {copied ? "Copied" : "Copy"}
                      </button>
                    </p>
                    <p className="billing-current-status">
                      {license.is_active
                        ? "Active — organizations can join with this code."
                        : "Paused — new organizations cannot join; existing members keep coverage."}
                      {license.rotated_at && ` Last rotated ${fmtDate(license.rotated_at)}.`}
                    </p>
                    <p className="billing-current-status">
                      Members run on your {data.backing_service_level_label} plan.{" "}
                      {license.member_count} member
                      {license.member_count === 1 ? "" : "s"}
                      {license.max_members != null && ` of ${license.max_members}`}.
                    </p>
                    <div className="inbox-actions">
                      <button
                        type="button"
                        className="dashboard-btn"
                        disabled={busy}
                        onClick={() => setActive(!license.is_active)}
                      >
                        {license.is_active ? "Pause code" : "Re-enable code"}
                      </button>
                      <button
                        type="button"
                        className="dashboard-btn"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Issue a new code? The current code stops working immediately. Existing members are unaffected."
                            )
                          ) {
                            rotate();
                          }
                        }}
                      >
                        Rotate code
                      </button>
                    </div>
                  </div>
                </section>

                {pooled && (
                  <section className="billing-current">
                    <h2 className="billing-section-title">
                      Pooled usage this period
                      <span className="billing-pooled-note">
                        {" "}
                        · {fmtDate(pooled.period_start)} – {fmtDate(pooled.period_end)}
                      </span>
                    </h2>
                    <div className="billing-current-card">
                      <p className="billing-current-status">
                        Meetings started: {meter(pooled.meetings_started)}
                      </p>
                      <p className="billing-current-status">
                        Survey responses: {meter(pooled.survey_submissions)}
                      </p>
                      <p className="billing-current-status">
                        AI meeting runs: {meter(pooled.ai_meeting_runs)}
                      </p>
                      <p className="billing-current-status">
                        Board posts: {meter(pooled.board_posts)}
                      </p>
                    </div>
                  </section>
                )}

                <section className="billing-current">
                  <h2 className="billing-section-title">Member organizations</h2>
                  {data.members.length === 0 ? (
                    <p className="dashboard-empty">
                      No members yet. Share the code above with organizations you want
                      to cover.
                    </p>
                  ) : (
                    <div className="billing-current-card umbrella-table-wrap">
                      <table className="umbrella-table">
                        <thead>
                          <tr>
                            <th>Organization</th>
                            <th>Joined</th>
                            <th>Meetings</th>
                            <th>Survey responses</th>
                            <th>AI runs</th>
                            <th>Board posts</th>
                            <th aria-label="Actions" />
                          </tr>
                        </thead>
                        <tbody>
                          {data.members.map((m) => (
                            <tr key={m.relationship_id}>
                              <td>
                                <Link to={`/org/${m.organization.slug}`}>
                                  {m.organization.name}
                                </Link>
                              </td>
                              <td>{fmtDate(m.joined_at)}</td>
                              <td>{m.usage.meetings_started}</td>
                              <td>{m.usage.survey_submissions}</td>
                              <td>{m.usage.ai_meeting_runs}</td>
                              <td>{m.usage.board_posts}</td>
                              <td>
                                <button
                                  type="button"
                                  className="dashboard-btn dashboard-btn--danger"
                                  disabled={busy}
                                  onClick={() => removeMember(m)}
                                >
                                  Remove
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="dashboard-meta">
                        Counts are each member&apos;s share of the current period. Members
                        can also see their own share on their Billing page.
                      </p>
                    </div>
                  )}
                </section>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
