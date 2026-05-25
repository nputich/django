import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import AppLayout from "../components/layout/AppLayout";
import OrganizationSearch from "../components/organization/OrganizationSearch";
import OrganizationCard from "../components/organization/OrganizationCard";
import "../styles/OrganizationLanding.css";

function OrganizationLanding() {
  const { code: routeCode } = useParams();
  const navigate = useNavigate();
  const [code, setCode] = useState(routeCode || "");
  const [organization, setOrganization] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const lookup = useCallback(
    async (searchCode) => {
      const trimmed = searchCode.trim();
      if (!trimmed) {
        setError("Please enter an organization code.");
        setOrganization(null);
        return;
      }

      setLoading(true);
      setError(null);
      setOrganization(null);

      try {
        const res = await api.get(
          `/api/organizations/${encodeURIComponent(trimmed)}/`
        );
        setOrganization(res.data);
        navigate(`/org/${encodeURIComponent(res.data.code)}`, {
          replace: true,
        });
      } catch (err) {
        if (err.response?.status === 404) {
          setError(`No organization found for "${trimmed.toUpperCase()}".`);
        } else {
          setError("Something went wrong. Please try again.");
        }
      } finally {
        setLoading(false);
      }
    },
    [navigate]
  );

  useEffect(() => {
    if (routeCode) {
      setCode(routeCode);
      lookup(routeCode);
    } else {
      setOrganization(null);
      setError(null);
    }
  }, [routeCode, lookup]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (trimmed) {
      navigate(`/org/${encodeURIComponent(trimmed)}`);
    } else {
      setError("Please enter an organization code.");
    }
  };

  return (
    <AppLayout>
      <section className="landing-hero">
        <p className="landing-eyebrow">Community lookup</p>
        <h1 className="landing-title">Find your organization</h1>
        <p className="landing-subtitle">
          Enter the code your group shared to view their communib profile.
        </p>
        <OrganizationSearch
          code={code}
          onCodeChange={setCode}
          onSubmit={handleSubmit}
          loading={loading}
        />
        {error && (
          <p className="landing-error" role="alert">
            {error}
          </p>
        )}
        {organization && <OrganizationCard organization={organization} />}
      </section>
    </AppLayout>
  );
}

export default OrganizationLanding;
