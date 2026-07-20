import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
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

export default function OrgBoardPage() {
  const { slug } = useParams();
  const [boardData, setBoardData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadBoard = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get(`/api/organizations/${slug}/board/`);
      setBoardData(res.data);
    } catch (err) {
      setBoardData(null);
      setError(err.response?.data?.detail || "Could not load this board.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

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
        <Link to={`/org/${slug}/hub`} className="dashboard-back">
          ← Back to {boardData?.organization_name || "organization"}
        </Link>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {boardData && (
          <div className="dashboard-card">
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
          </div>
        )}
      </main>
    </div>
  );
}
