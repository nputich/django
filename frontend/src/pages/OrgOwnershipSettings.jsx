import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import { claimAccessPath } from "../constants/orgCreation";
import "../styles/Dashboard.css";
import "../styles/OrgLifecycle.css";

export default function OrgOwnershipSettings() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [transferUserId, setTransferUserId] = useState("");
  const [closeConfirm, setCloseConfirm] = useState("");
  const [showCloseForm, setShowCloseForm] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/ownership/`)
      .then((res) => {
        setData(res.data);
        const first = res.data.transfer_candidates?.[0];
        setTransferUserId(first ? String(first.user_id) : "");
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not load ownership settings."
        );
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (fn) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p className="dashboard-empty">Loading...</p>
        </main>
      </div>
    );
  }

  const isOwner = data?.membership?.is_owner;
  const lifecycle = data?.lifecycle || {};
  const activeService = data?.active_service;
  const hasPaid = Boolean(activeService);
  const periodEnd = activeService?.current_period_end
    ? new Date(activeService.current_period_end).toLocaleDateString()
    : null;

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Ownership &amp; Organization</h1>
          <p>{data?.organization?.name}</p>
        </div>

        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {lifecycle.status === "closure_pending" && (
          <div className="dashboard-card">
            <h2>Organization scheduled to close</h2>
            <p>
              Organization scheduled to close on{" "}
              <strong>
                {lifecycle.closure_effective_at
                  ? new Date(lifecycle.closure_effective_at).toLocaleDateString()
                  : "the paid-through date"}
              </strong>
              .
            </p>
            {isOwner && (
              <button
                type="button"
                className="dashboard-btn dashboard-btn--primary"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const res = await api.post(
                      `/api/organizations/${slug}/cancel-closure/`
                    );
                    setMessage(res.data.detail);
                  })
                }
              >
                Cancel Organization Closure
              </button>
            )}
          </div>
        )}

        <section className="dashboard-card">
          <h2>Ownership</h2>
          <p className="dashboard-meta">
            Your role: <strong>{data?.membership?.role || "—"}</strong>
            {" · "}
            Owners: {data?.membership?.owner_count ?? 0}
          </p>

          {isOwner ? (
            <>
              <div className="dashboard-field">
                <label htmlFor="transfer-owner">Transfer Ownership</label>
                <select
                  id="transfer-owner"
                  value={transferUserId}
                  onChange={(e) => setTransferUserId(e.target.value)}
                  disabled={!data?.transfer_candidates?.length}
                >
                  {!data?.transfer_candidates?.length && (
                    <option value="">No other administrators available</option>
                  )}
                  {data?.transfer_candidates?.map((c) => (
                    <option key={c.user_id} value={c.user_id}>
                      {c.username} ({c.role})
                    </option>
                  ))}
                </select>
              </div>
              <div className="dashboard-actions">
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy || !transferUserId}
                  onClick={() =>
                    run(async () => {
                      const res = await api.post(
                        `/api/organizations/${slug}/ownership/transfer/`,
                        { new_owner_user_id: Number(transferUserId) }
                      );
                      setMessage(res.data.detail || "Ownership transferred.");
                      navigate(`/dashboard/${slug}`);
                    })
                  }
                >
                  Transfer Ownership
                </button>
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      const res = await api.post(
                        `/api/organizations/${slug}/ownership/cancel/`
                      );
                      setMessage(res.data.detail);
                      navigate("/dashboard");
                    })
                  }
                >
                  Cancel My Ownership
                </button>
              </div>
              <p className="dashboard-meta">
                If you are the only owner, transfer ownership or close the
                organization instead of canceling ownership.
              </p>
            </>
          ) : (
            <p className="dashboard-meta">
              Only the organization owner can transfer or cancel ownership.
            </p>
          )}
        </section>

        <section className="dashboard-card">
          <h2>Subscription</h2>
          <p className="dashboard-meta">
            Current service:{" "}
            <strong>{data?.billing?.name || data?.billing?.service_level}</strong>
            {activeService?.cancel_at_period_end && periodEnd
              ? ` · Cancels at end of period (${periodEnd})`
              : null}
          </p>
          <div className="dashboard-actions">
            <Link
              to={`/dashboard/${slug}/billing`}
              className="dashboard-btn dashboard-btn--primary"
            >
              Change Service Level
            </Link>
            {isOwner && hasPaid && !activeService?.cancel_at_period_end && (
              <button
                type="button"
                className="dashboard-btn"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const res = await api.post(
                      `/api/organizations/${slug}/billing/cancel/`
                    );
                    setMessage(res.data.detail);
                  })
                }
              >
                Cancel Paid Service
              </button>
            )}
          </div>
          <p className="dashboard-meta">
            Canceling paid service does not close the organization. You keep
            your profile, history, and Free Organization features after the
            paid period ends.
          </p>
        </section>

        {isOwner && lifecycle.status !== "closed" && (
          <section className="dashboard-card dashboard-danger-zone">
            <h2>Organization Status</h2>
            <p>
              Closing removes the organization from the CommuniB directory and
              prevents new activity. Existing records may be retained for
              account integrity, billing, reporting, restoration, and abuse
              prevention.
            </p>
            {!showCloseForm ? (
              <button
                type="button"
                className="dashboard-btn dashboard-btn--danger"
                onClick={() => setShowCloseForm(true)}
              >
                Close Organization
              </button>
            ) : (
              <div>
                <h3>Close this organization?</h3>
                <p>
                  Closing this organization will remove it from the CommuniB
                  directory and prevent new activity. Existing records may be
                  retained for account integrity, billing, reporting,
                  restoration, and abuse prevention.
                </p>
                {hasPaid && (
                  <p>
                    If this organization has paid service, future renewal will
                    also be canceled
                    {periodEnd
                      ? `, and the organization will remain active until ${periodEnd}`
                      : ""}
                    .
                  </p>
                )}
                <div className="dashboard-field">
                  <label htmlFor="close-confirm">
                    Type &quot;{data.organization.name}&quot; to confirm.
                  </label>
                  <input
                    id="close-confirm"
                    value={closeConfirm}
                    onChange={(e) => setCloseConfirm(e.target.value)}
                    autoComplete="off"
                  />
                </div>
                <div className="dashboard-actions">
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => {
                      setShowCloseForm(false);
                      setCloseConfirm("");
                    }}
                  >
                    Not now
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--danger"
                    disabled={busy || closeConfirm !== data.organization.name}
                    onClick={() =>
                      run(async () => {
                        const res = await api.post(
                          `/api/organizations/${slug}/close/`,
                          { confirmation_name: closeConfirm }
                        );
                        setMessage(res.data.detail);
                        setShowCloseForm(false);
                        setCloseConfirm("");
                      })
                    }
                  >
                    Close Organization
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {lifecycle.status === "closed" && (
          <div className="dashboard-card">
            <h2>Organization closed</h2>
            <p>
              This organization is archived. To restore it, contact CommuniB or
              use Claim Access.
            </p>
            <Link
              to={claimAccessPath({
                name: data.organization.name,
                slug: data.organization.slug,
              })}
              className="dashboard-btn"
            >
              Request Access / Restoration
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}
