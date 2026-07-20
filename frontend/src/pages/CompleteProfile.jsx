import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import ProfileForm from "../components/ProfileForm";
import "../styles/Dashboard.css";
import "../styles/Board.css";

export default function CompleteProfile() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/api/me/")
      .then((res) => {
        setProfile(res.data);
        if (res.data.profile_complete) {
          setRedirecting(true);
          navigate("/dashboard", {
            replace: true,
            state: { profileComplete: true },
          });
        }
      })
      .catch(() => setError("Could not load your profile."))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleSaved = async (data) => {
    setProfile(data);
    if (data.profile_complete) {
      setRedirecting(true);
      navigate("/dashboard", {
        replace: true,
        state: { profileComplete: true },
      });
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <div className="dashboard-header">
          <h1>Complete your profile</h1>
          <p>
            Before using your dashboard, please add your name and username. Other
            fields are optional and can be updated later.
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {redirecting && (
          <p className="dashboard-empty">Profile saved. Opening your dashboard...</p>
        )}
        {error && <p className="dashboard-error">{error}</p>}

        {profile && !profile.profile_complete && !redirecting && (
          <div className="dashboard-card">
            <ProfileForm
              initial={profile}
              onSaved={handleSaved}
              submitLabel="Continue to dashboard"
              requireRequiredFields
            />
          </div>
        )}
      </main>
    </div>
  );
}
