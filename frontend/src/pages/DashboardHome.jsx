import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import PostingBoard from "../components/PostingBoard";
import "../styles/Dashboard.css";
import "../styles/Board.css";

export default function DashboardHome() {
  const [organizations, setOrganizations] = useState([]);
  const [profile, setProfile] = useState(null);
  const [boardData, setBoardData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadBoard = useCallback(async () => {
    const res = await api.get("/api/me/board/");
    setBoardData(res.data);
  }, []);

  useEffect(() => {
    Promise.all([
      api.get("/api/me/organizations/"),
      api.get("/api/me/"),
      api.get("/api/me/board/"),
    ])
      .then(([orgsRes, meRes, boardRes]) => {
        setOrganizations(orgsRes.data.organizations ?? []);
        setProfile(meRes.data);
        setBoardData(boardRes.data);
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail || "Could not load your dashboard."
        );
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCreatePost = async (payload) => {
    await api.post("/api/me/board/", payload);
    await loadBoard();
  };

  const handleDeletePost = async (postId) => {
    if (!window.confirm("Delete this post?")) return;
    await api.delete(`/api/me/board/posts/${postId}/`);
    await loadBoard();
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <div className="dashboard-header">
          <h1>
            {profile?.display_name
              ? `Welcome, ${profile.display_name}`
              : "Your dashboard"}
          </h1>
          <p>
            Your personal posting board and organizations you manage.
            <Link to="/account" style={{ marginLeft: "0.5rem" }}>
              Account settings
            </Link>
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {boardData && (
          <div className="dashboard-card">
            <PostingBoard
              title={boardData.title || "My board"}
              postingModeLabel="Private (restricted)"
              posts={boardData.posts}
              canPost={boardData.can_post}
              onCreatePost={handleCreatePost}
              onDeletePost={handleDeletePost}
              emptyMessage="Your personal board is empty. Add a note for yourself."
            />
          </div>
        )}

        {!loading && !error && organizations.length === 0 && (
          <div className="dashboard-card">
            <p className="dashboard-empty">
              You are not an admin of any organization yet. Ask a site
              administrator to add you as an organization admin.
            </p>
          </div>
        )}

        {!loading && organizations.length > 0 && (
          <>
            <h2 className="dashboard-section-title">Your organizations</h2>
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
          </>
        )}
      </main>
    </div>
  );
}
