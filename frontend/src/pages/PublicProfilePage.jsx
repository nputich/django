import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import { ensureValidSession } from "../auth";
import "../styles/Dashboard.css";
import "../styles/PublicProfile.css";

export default function PublicProfilePage() {
  const { username } = useParams();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [pictureBroken, setPictureBroken] = useState(false);
  const signedIn = ensureValidSession();

  useEffect(() => {
    setLoading(true);
    setError("");
    setPictureBroken(false);
    api
      .get(`/api/users/${encodeURIComponent(username)}/`)
      .then((res) => setProfile(res.data))
      .catch(() => setError("Account not found."))
      .finally(() => setLoading(false));
  }, [username]);

  const showPicture = Boolean(profile?.profile_picture_url) && !pictureBroken;

  return (
    <div className="dashboard">
      {signedIn ? <AppHeader /> : null}
      <main className="dashboard-main public-profile-page">
        <Link
          to={signedIn ? "/dashboard/inbox" : "/"}
          className="dashboard-back"
        >
          {signedIn ? "← Back to inbox" : "← Back to home"}
        </Link>

        {loading && <p className="dashboard-empty">Loading…</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {profile && (
          <div className="dashboard-card public-profile-card">
            <div className="public-profile-header">
              {showPicture ? (
                <img
                  src={profile.profile_picture_url}
                  alt=""
                  className="public-profile-avatar"
                  onError={() => setPictureBroken(true)}
                />
              ) : (
                <div className="public-profile-avatar public-profile-avatar--empty">
                  {(profile.display_name || profile.username || "?").slice(0, 1)}
                </div>
              )}
              <div>
                <h1>{profile.display_name || profile.username}</h1>
                <p className="public-profile-username">@{profile.username}</p>
              </div>
            </div>

            {(profile.city || profile.state) && (
              <p className="public-profile-location">
                {[profile.city, profile.state].filter(Boolean).join(", ")}
              </p>
            )}

            {signedIn && (
              <div className="public-profile-actions">
                <Link
                  to={`/dashboard/inbox?to=${encodeURIComponent(profile.username)}`}
                  className="dashboard-btn dashboard-btn--primary"
                >
                  Message @{profile.username}
                </Link>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
