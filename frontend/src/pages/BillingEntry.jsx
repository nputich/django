import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/Billing.css";

/**
 * Alias for future PayPal return URLs (`/dashboard/billing?paypal=success`).
 * Stage 1: pick an admin organization, or redirect when only one exists / ?org= is set.
 */
export default function BillingEntry() {
  const [searchParams] = useSearchParams();
  const orgParam = searchParams.get("org") || "";
  const [organizations, setOrganizations] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/me/organizations/")
      .then((res) => setOrganizations(res.data.organizations ?? []))
      .catch((err) => {
        setError(
          err.response?.data?.detail || "Could not load your organizations."
        );
        setOrganizations([]);
      });
  }, []);

  if (orgParam) {
    const qs = searchParams.toString();
    const suffix = qs ? `?${qs}` : "";
    return <Navigate to={`/dashboard/${orgParam}/billing${suffix}`} replace />;
  }

  if (organizations === null && !error) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p className="dashboard-empty">Loading...</p>
        </main>
      </div>
    );
  }

  if (organizations && organizations.length === 1) {
    const qs = searchParams.toString();
    const suffix = qs ? `?${qs}` : "";
    return (
      <Navigate
        to={`/dashboard/${organizations[0].slug}/billing${suffix}`}
        replace
      />
    );
  }

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main billing-page">
        <Link to="/dashboard" className="dashboard-back">
          ← All organizations
        </Link>
        <div className="dashboard-header">
          <h1>Billing &amp; Service</h1>
          <p>Select an organization to manage billing.</p>
        </div>
        {error && <p className="dashboard-error">{error}</p>}
        {organizations && organizations.length === 0 && !error && (
          <p className="dashboard-empty">
            You do not administer any organizations yet.
          </p>
        )}
        {organizations && organizations.length > 0 && (
          <ul className="billing-org-picker">
            {organizations.map((org) => (
              <li key={org.slug}>
                <Link
                  to={`/dashboard/${org.slug}/billing`}
                  className="dashboard-btn dashboard-btn--primary"
                >
                  {org.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
