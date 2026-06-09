import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

export default function DashboardHome() {
  const [organizations, setOrganizations] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/api/me/organizations/")
      .then((res) => setOrganizations(res.data.organizations ?? []))
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not load your organizations."
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <div className="dashboard-header">
          <h1>Organization dashboard</h1>
          <p>Manage surveys and meetings for organizations you own.</p>
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {!loading && !error && organizations.length === 0 && (
          <div className="dashboard-card">
            <p className="dashboard-empty">
              You are not an admin of any organization yet. Ask a site
              administrator to add you as an organization admin, or create an
              organization in Django admin.
            </p>
          </div>
        )}

        {!loading && organizations.length > 0 && (
          <div className="dashboard-org-picker">
            {organizations.map((org) => (
              <Link
                key={org.id}
                to={`/dashboard/${org.slug}`}
                className="dashboard-org-link"
              >
                <strong>{org.name}</strong>
                <span>{org.description || `/${org.slug}`}</span>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
