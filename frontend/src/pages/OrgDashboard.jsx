import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import DashboardCollapsibleSection from "../components/DashboardCollapsibleSection";
import PostingBoard from "../components/PostingBoard";
import "../styles/Dashboard.css";
import "../styles/Board.css";

function readOnlyMessage(postingMode, isAdmin) {
  if (postingMode === "restricted" && !isAdmin) {
    return "This board is restricted. Only organization admins can create posts; logged-in users can reply.";
  }
  if (postingMode === "members_only") {
    return "Only organization members can post and reply on this board.";
  }
  return "Sign in to post or reply on this board.";
}

export default function OrgDashboard() {
  const { slug } = useParams();
  const [org, setOrg] = useState(null);
  const [boardData, setBoardData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [boardLoading, setBoardLoading] = useState(true);
  const [startingId, setStartingId] = useState(null);
  const [boardTitle, setBoardTitle] = useState("");
  const [boardMode, setBoardMode] = useState("public");
  const [boardSaving, setBoardSaving] = useState(false);
  const [boardMessage, setBoardMessage] = useState("");

  const loadDashboard = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/dashboard/`)
      .then((res) => {
        setOrg(res.data);
        if (res.data.board) {
          setBoardTitle(res.data.board.title || "");
          setBoardMode(res.data.board.posting_mode || "public");
        }
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not load this organization dashboard."
        );
      })
      .finally(() => setLoading(false));
  }, [slug]);

  const loadBoard = useCallback(() => {
    setBoardLoading(true);
    return api
      .get(`/api/organizations/${slug}/board/`)
      .then((res) => setBoardData(res.data))
      .catch((err) => {
        setBoardData(null);
        setError(err.response?.data?.detail || "Could not load this posting board.");
      })
      .finally(() => setBoardLoading(false));
  }, [slug]);

  useEffect(() => {
    loadDashboard();
    loadBoard();
  }, [loadDashboard, loadBoard]);

  const handleStartMeeting = async (meetingId) => {
    setStartingId(meetingId);
    try {
      await api.post(`/api/organizations/${slug}/meetings/${meetingId}/start/`);
      await loadDashboard();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not start meeting.");
    } finally {
      setStartingId(null);
    }
  };

  const handleSaveBoardSettings = async (e) => {
    e.preventDefault();
    setBoardSaving(true);
    setBoardMessage("");
    try {
      await api.patch(`/api/organizations/${slug}/board/settings/`, {
        title: boardTitle,
        posting_mode: boardMode,
      });
      setBoardMessage("Board settings saved.");
      await loadDashboard();
      await loadBoard();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save board settings.");
    } finally {
      setBoardSaving(false);
    }
  };

  const handleCreatePost = async (payload) => {
    await api.post(`/api/organizations/${slug}/board/`, payload);
    await loadBoard();
  };

  const handleDeletePost = async (postId) => {
    if (!window.confirm("Delete this post?")) return;
    await api.delete(`/api/organizations/${slug}/board/posts/${postId}/`);
    await loadBoard();
  };

  const handleCreateReply = async (postId, payload) => {
    await api.post(`/api/organizations/${slug}/board/posts/${postId}/replies/`, payload);
    await loadBoard();
  };

  const handleDeleteReply = async (postId, replyId) => {
    if (!window.confirm("Delete this reply?")) return;
    await api.delete(
      `/api/organizations/${slug}/board/posts/${postId}/replies/${replyId}/`
    );
    await loadBoard();
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← All organizations
        </Link>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {org && (
          <>
            <div className="dashboard-header">
              <h1>{org.name}</h1>
              <p>{org.description || "Organization dashboard"}</p>
            </div>

            <div className="dashboard-actions">
              <Link
                to={`/dashboard/${slug}/surveys/new`}
                className="dashboard-btn dashboard-btn--primary"
              >
                Create survey
              </Link>
              <Link
                to={`/dashboard/${slug}/meetings/new`}
                className="dashboard-btn dashboard-btn--primary"
              >
                Create meeting
              </Link>
              <Link
                to={`/org/${slug}/hub`}
                className="dashboard-btn"
                target="_blank"
                rel="noopener noreferrer"
              >
                View public hub
              </Link>
            </div>

            <DashboardCollapsibleSection id="org-board" title="Posting board" defaultOpen>
              <p className="dashboard-meta">
                Control who can post on your organization&apos;s public board.
              </p>
              <form className="dashboard-form" onSubmit={handleSaveBoardSettings}>
                <div className="dashboard-field">
                  <label htmlFor="board-title">Board title</label>
                  <input
                    id="board-title"
                    value={boardTitle}
                    onChange={(e) => setBoardTitle(e.target.value)}
                  />
                </div>
                <div className="dashboard-field">
                  <label htmlFor="board-mode">Who can post</label>
                  <select
                    id="board-mode"
                    value={boardMode}
                    onChange={(e) => setBoardMode(e.target.value)}
                  >
                    <option value="public">Everyone (logged in)</option>
                    <option value="members_only">Members only</option>
                    <option value="restricted">Restricted (admins only)</option>
                  </select>
                </div>
                {boardMessage && (
                  <p className="dashboard-success" style={{ margin: 0 }}>
                    {boardMessage}
                  </p>
                )}
                <button
                  type="submit"
                  className="dashboard-btn dashboard-btn--primary"
                  disabled={boardSaving}
                >
                  {boardSaving ? "Saving..." : "Save board settings"}
                </button>
              </form>
              {boardLoading && <p className="dashboard-empty">Loading board...</p>}
              {boardData && (
                <PostingBoard
                  title={boardData.board?.title || `${boardData.organization_name} board`}
                  postingMode={boardData.board?.posting_mode}
                  postingModeLabel={boardData.board?.posting_mode_label}
                  posts={boardData.posts}
                  canPost={boardData.can_post}
                  canReply={boardData.can_reply}
                  readOnlyMessage={
                    boardData.can_post
                      ? ""
                      : readOnlyMessage(boardData.board?.posting_mode, boardData.is_admin)
                  }
                  onCreatePost={boardData.can_post ? handleCreatePost : undefined}
                  onCreateReply={boardData.can_reply ? handleCreateReply : undefined}
                  onDeletePost={handleDeletePost}
                  onDeleteReply={handleDeleteReply}
                />
              )}
            </DashboardCollapsibleSection>

            <DashboardCollapsibleSection id="org-surveys" title="Surveys">
              {org.surveys.length === 0 ? (
                <p className="dashboard-empty">No surveys yet.</p>
              ) : (
                <ul className="dashboard-list">
                  {org.surveys.map((survey) => (
                    <li key={survey.id} className="dashboard-list-item">
                      <div>
                        <h3>{survey.title}</h3>
                        <p className="dashboard-meta">
                          {survey.is_active ? "Active" : "Inactive"} ·{" "}
                          <Link to={`/s/${survey.id}`}>Open survey</Link> ·{" "}
                          <Link to={`/dashboard/${slug}/surveys/${survey.id}/edit`}>
                            Edit
                          </Link>
                        </p>
                      </div>
                      <div>
                        {(survey.access_codes ?? []).map((code) => (
                          <span key={code.id} className="dashboard-code">
                            {code.code}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </DashboardCollapsibleSection>

            <DashboardCollapsibleSection id="org-meetings" title="Meetings">
              {org.meetings.length === 0 ? (
                <p className="dashboard-empty">No meetings yet.</p>
              ) : (
                <ul className="dashboard-list">
                  {org.meetings.map((meeting) => (
                    <li key={meeting.id} className="dashboard-list-item">
                      <div>
                        <h3>{meeting.title}</h3>
                        <p className="dashboard-meta">
                          {meeting.access_mode} · {meeting.status} ·{" "}
                          <Link to={`/m/${meeting.id}`}>Open meeting</Link> ·{" "}
                          <Link to={`/dashboard/${slug}/meetings/${meeting.id}/edit`}>
                            Edit
                          </Link>
                        </p>
                        {meeting.status === "scheduled" && (
                          <button
                            type="button"
                            className="dashboard-btn dashboard-btn--primary"
                            style={{ marginTop: "0.5rem" }}
                            disabled={startingId === meeting.id}
                            onClick={() => handleStartMeeting(meeting.id)}
                          >
                            {startingId === meeting.id ? "Starting..." : "Start meeting"}
                          </button>
                        )}
                        <Link
                          to={`/dashboard/${slug}/meetings/${meeting.id}/host`}
                          className="dashboard-btn"
                          style={{ marginTop: "0.5rem", display: "inline-flex" }}
                        >
                          Host controls
                        </Link>
                      </div>
                      <div>
                        {(meeting.access_codes ?? []).map((code) => (
                          <span key={code.id} className="dashboard-code">
                            {code.code}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </DashboardCollapsibleSection>
          </>
        )}
      </main>
    </div>
  );
}
