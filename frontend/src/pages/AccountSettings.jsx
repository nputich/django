import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import ProfileForm from "../components/ProfileForm";
import "../styles/Dashboard.css";
import "../styles/Board.css";

export default function AccountSettings() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/me/")
      .then((res) => setProfile(res.data))
      .catch(() => setError("Could not load your profile."))
      .finally(() => setLoading(false));
  }, []);

  const handleSaved = async (data) => {
    try {
      const res = await api.get("/api/me/");
      setProfile(res.data);
    } catch {
      setProfile(data);
    }
    setSuccess("Profile updated.");
    setTimeout(() => setSuccess(""), 3000);
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Account settings</h1>
          <p>Customize your profile. Name and username are required.</p>
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {success && <div className="dashboard-success">{success}</div>}

        {profile && (
          <div className="dashboard-card">
            <ProfileForm
              initial={profile}
              onSaved={handleSaved}
              submitLabel="Save changes"
              requireRequiredFields
            />
          </div>
        )}
      </main>
    </div>
  );
}
