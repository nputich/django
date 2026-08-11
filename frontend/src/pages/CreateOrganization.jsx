import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import MarketingLayout from "../components/MarketingLayout";
import { ensureValidSession } from "../auth";
import { PAID_PLAN_LEVELS, claimAccessPath } from "../constants/orgCreation";
import "../styles/Dashboard.css";
import "../styles/CreateOrganization.css";

const PLAN_LABELS = {
  [PAID_PLAN_LEVELS.BASIC]: "Basic",
  [PAID_PLAN_LEVELS.COMMUNITY]: "Community",
  [PAID_PLAN_LEVELS.COMMUNITY_PLUS]: "Community Plus",
};

export default function CreateOrganization() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const plan = (searchParams.get("plan") || "").toUpperCase();
  const intendedPlan = PLAN_LABELS[plan] ? plan : "";
  const initialName = searchParams.get("name") || "";
  const isSignedIn = ensureValidSession();

  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [closedConflict, setClosedConflict] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const planNote = useMemo(() => {
    if (!intendedPlan) return null;
    return (
      <>
        After you create your organization, you can continue to{" "}
        <strong>{PLAN_LABELS[intendedPlan]}</strong> billing.
      </>
    );
  }, [intendedPlan]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setClosedConflict(null);
    setSubmitting(true);
    try {
      const res = await api.post("/api/organizations/", {
        name: name.trim(),
        description: description.trim(),
      });
      const slug = res.data.slug;
      if (intendedPlan) {
        navigate(`/dashboard/${slug}/billing`, {
          replace: true,
          state: { intendedPlan },
        });
      } else {
        navigate(`/dashboard/${slug}`, { replace: true });
      }
    } catch (err) {
      const data = err.response?.data;
      if (data?.code === "closed_organization_exists" && data.organization) {
        setClosedConflict(data);
        setError(data.detail || "This organization previously existed on CommuniB.");
      } else if (err.response?.status === 401) {
        setError("Sign in to create an organization.");
      } else {
        const detail =
          data?.name?.[0] ||
          data?.detail ||
          (typeof data === "object" && data
            ? Object.values(data).flat()?.[0]
            : null) ||
          "Could not create the organization. Please try again.";
        setError(String(detail));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!isSignedIn) {
    const from = {
      pathname: location.pathname,
      search: location.search,
    };
    return (
      <MarketingLayout mainClassName="landing-main landing-main--centered">
        <main className="create-org-page create-org-page--gate">
          <h1>Create an Organization</h1>
          <p>
            You need a CommuniB account to create and manage an organization
            {intendedPlan
              ? ` (then you can upgrade to ${PLAN_LABELS[intendedPlan]})`
              : ""}
            .
          </p>
          <div className="dashboard-actions">
            <Link
              to="/"
              state={{ from }}
              className="dashboard-btn dashboard-btn--primary"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              state={{ from }}
              className="dashboard-btn"
            >
              Create an account
            </Link>
          </div>
          <p className="enter-code-alt">
            <Link to="/communities">← Back to communities</Link>
          </p>
        </main>
      </MarketingLayout>
    );
  }

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main create-org-page">
        <div className="dashboard-header">
          <p className="dashboard-back">
            <Link to="/dashboard">← Back to dashboard</Link>
          </p>
          <h1>Create an Organization</h1>
          <p>
            Start on the free organization plan. You can upgrade anytime from
            Billing &amp; Service.
          </p>
          {planNote && <p className="create-org-plan-note">{planNote}</p>}
        </div>

        <form className="create-org-form" onSubmit={handleSubmit}>
          <div className="create-org-field">
            <label htmlFor="org-name">Organization name</label>
            <input
              id="org-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              required
              autoFocus
              placeholder="e.g. Forsyth Example Organization"
            />
          </div>
          <div className="create-org-field">
            <label htmlFor="org-description">
              Short description <span>(optional)</span>
            </label>
            <textarea
              id="org-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              maxLength={5000}
              placeholder="What does this organization do?"
            />
          </div>
          {error && <p className="dashboard-error">{error}</p>}
          {closedConflict?.organization && (
            <div className="dashboard-card">
              <p>
                <strong>This organization previously existed on CommuniB.</strong>
              </p>
              <p>
                If you represent this organization, you can request access or
                restoration.
              </p>
              <div className="dashboard-actions">
                <Link
                  to={claimAccessPath(closedConflict.organization)}
                  className="dashboard-btn dashboard-btn--primary"
                >
                  Claim Organization / Request Access
                </Link>
                <button
                  type="button"
                  className="dashboard-btn"
                  onClick={async () => {
                    try {
                      await api.post(
                        `/api/organizations/${closedConflict.organization.slug}/claim-request/`,
                        { message: "Requesting restoration / access." }
                      );
                    } catch {
                      /* contact link remains available */
                    }
                  }}
                >
                  Record claim request
                </button>
              </div>
            </div>
          )}
          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting || name.trim().length < 2}
          >
            {submitting ? "Creating…" : "Create organization"}
          </button>
        </form>
      </main>
    </div>
  );
}
