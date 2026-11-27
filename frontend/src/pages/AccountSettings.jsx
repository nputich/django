import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import DashboardCollapsibleSection from "../components/DashboardCollapsibleSection";
import OrgAccountFieldsForm from "../components/OrgAccountFieldsForm";
import ProfileForm from "../components/ProfileForm";
import YouTubeChannelsSection from "../components/YouTubeChannelsSection";
import "../styles/Dashboard.css";
import "../styles/Board.css";

export default function AccountSettings() {
  const location = useLocation();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    api
      .get("/api/me/")
      .then((res) => setProfile(res.data))
      .catch(() => setError("Could not load your profile."));

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  const handlePersonalSaved = async (data) => {
    try {
      const res = await api.get("/api/me/");
      setProfile(res.data);
    } catch {
      setProfile(data);
    }
    setSuccess("Profile updated.");
    setTimeout(() => setSuccess(""), 3000);
  };

  const handleOrgSaved = async (section) => {
    if (section?.organization_slug) {
      setProfile((prev) => {
        if (!prev) return prev;
        const sections = prev.organization_sections || [];
        const next = sections.map((s) =>
          s.organization_slug === section.organization_slug ? section : s
        );
        return { ...prev, organization_sections: next };
      });
    } else {
      await load();
    }
    setSuccess("Organization fields updated.");
    setTimeout(() => setSuccess(""), 3000);
  };

  const orgSections = profile?.organization_sections || [];
  const hashTarget = (location.hash || "").replace(/^#/, "");
  const youtubeOpen =
    !hashTarget ||
    hashTarget === "youtube-channels" ||
    (location.search || "").includes("youtube=");

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Account settings</h1>
          <p>
            Your personal CommuniBetter account: profile, YouTube channels, then
            organization-specific fields.
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {success && <div className="dashboard-success">{success}</div>}

        {profile && (
          <DashboardCollapsibleSection
            id="personal-profile"
            title="Personal profile"
            defaultOpen={
              !hashTarget || hashTarget === "personal-profile"
            }
          >
            <ProfileForm
              initial={profile}
              onSaved={handlePersonalSaved}
              submitLabel="Save changes"
              requireRequiredFields
            />
          </DashboardCollapsibleSection>
        )}

        {profile && (
          <DashboardCollapsibleSection
            id="youtube-channels"
            title="YouTube channels"
            defaultOpen={youtubeOpen}
          >
            <YouTubeChannelsSection />
          </DashboardCollapsibleSection>
        )}

        {profile && orgSections.length > 0 && (
          <div className="dashboard-header" style={{ marginTop: "1.5rem" }}>
            <h2 className="dashboard-section-title">Organizations</h2>
            <p className="dashboard-meta">
              Expand an organization to edit fields shared with it.
            </p>
          </div>
        )}

        {profile &&
          orgSections.map((section) => {
            const sectionId = `org-account-${section.organization_slug}`;
            return (
              <DashboardCollapsibleSection
                key={section.organization_slug}
                id={sectionId}
                title={section.organization_name}
                defaultOpen={hashTarget === sectionId}
              >
                <OrgAccountFieldsForm
                  section={section}
                  onSaved={handleOrgSaved}
                />
              </DashboardCollapsibleSection>
            );
          })}
      </main>
    </div>
  );
}
