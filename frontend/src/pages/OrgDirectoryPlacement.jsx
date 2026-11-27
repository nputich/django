import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import DirectoryPlacementFields, {
  placementFromApi,
  placementToApiPayload,
} from "../components/DirectoryPlacementFields";
import "../styles/Dashboard.css";
import "../styles/CreateOrganization.css";

export default function OrgDirectoryPlacement() {
  const { slug } = useParams();
  const [orgName, setOrgName] = useState("");
  const [communityCode, setCommunityCode] = useState("");
  const [placement, setPlacement] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/directory-placement/`)
      .then((res) => {
        setOrgName(res.data.organization?.name || "");
        setCommunityCode(res.data.community_code || "");
        setPlacement(placementFromApi(res.data.directory_placement));
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail || "Could not load directory placement."
        );
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!placement) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const res = await api.patch(
        `/api/organizations/${slug}/directory-placement/`,
        placementToApiPayload(placement)
      );
      setMessage(res.data.detail || "Directory placement saved.");
      setPlacement(placementFromApi(res.data.directory_placement));
      setCommunityCode(res.data.community_code || communityCode);
    } catch (err) {
      setError(
        err.response?.data?.detail || "Could not save directory placement."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main create-org-page create-org-page--wide">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to organization
        </Link>
        <div className="dashboard-header">
          <h1>Directory Placement</h1>
          <p>
            {orgName
              ? `Choose where ${orgName} appears in Explore Communities.`
              : "Choose where this organization appears in Explore Communities."}
          </p>
          {communityCode && (
            <p className="dashboard-meta">
              Community Code: <strong className="dashboard-code">{communityCode}</strong>
            </p>
          )}
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {!loading && placement && (
          <form className="create-org-form" onSubmit={handleSave}>
            <h2 className="create-org-section-title">
              Where should this community appear?
            </h2>
            <DirectoryPlacementFields
              value={placement}
              onChange={setPlacement}
              idPrefix="edit-placement"
            />
            <button
              type="submit"
              className="dashboard-btn dashboard-btn--primary"
              disabled={saving || !placement.primary_subcategory_id}
            >
              {saving ? "Saving…" : "Save Directory Placement"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
