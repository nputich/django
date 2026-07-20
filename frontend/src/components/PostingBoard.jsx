import { useState } from "react";
import "../styles/Board.css";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

export default function PostingBoard({
  title,
  postingMode,
  postingModeLabel,
  posts = [],
  canPost,
  canReply,
  readOnlyMessage,
  onCreatePost,
  onCreateReply,
  onDeletePost,
  onDeleteReply,
  emptyMessage = "No posts yet.",
}) {
  const [postTitle, setPostTitle] = useState("");
  const [postBody, setPostBody] = useState("");
  const [replyBodies, setReplyBodies] = useState({});
  const [replyErrors, setReplyErrors] = useState({});
  const [submittingReplyId, setSubmittingReplyId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canPost || !onCreatePost) return;
    setSubmitting(true);
    setFormError("");
    try {
      await onCreatePost({ title: postTitle.trim(), body: postBody.trim() });
      setPostTitle("");
      setPostBody("");
    } catch (err) {
      setFormError(err.response?.data?.detail || "Could not save post.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReplySubmit = async (e, postId) => {
    e.preventDefault();
    if (!canReply || !onCreateReply) return;
    const body = (replyBodies[postId] || "").trim();
    if (!body) return;
    setSubmittingReplyId(postId);
    setReplyErrors((current) => ({ ...current, [postId]: "" }));
    try {
      await onCreateReply(postId, { body });
      setReplyBodies((current) => ({ ...current, [postId]: "" }));
    } catch (err) {
      setReplyErrors((current) => ({
        ...current,
        [postId]: err.response?.data?.detail || "Could not save reply.",
      }));
    } finally {
      setSubmittingReplyId(null);
    }
  };

  return (
    <section className="posting-board">
      <div className="posting-board-header">
        <h2>{title || "Posting board"}</h2>
        {postingModeLabel && (
          <span className="posting-board-mode">{postingModeLabel}</span>
        )}
      </div>

      {!canPost && readOnlyMessage && (
        <p className="posting-board-readonly">{readOnlyMessage}</p>
      )}

      {posts.length === 0 ? (
        <p className="dashboard-empty">{emptyMessage}</p>
      ) : (
        <ul className="posting-board-list">
          {posts.map((post) => (
            <li key={post.id} className="posting-board-item">
              <div className="posting-board-item-header">
                {post.author ? (
                  <div className="posting-board-author">
                    {post.author.profile_picture_url && (
                      <img
                        src={post.author.profile_picture_url}
                        alt=""
                        className="posting-board-avatar"
                      />
                    )}
                    <div>
                      <strong>
                        {post.author.display_name || post.author.username || "Member"}
                      </strong>
                      {post.author.username && (
                        <span className="posting-board-username">
                          @{post.author.username}
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <span />
                )}
                <time className="posting-board-date">{formatDate(post.created_at)}</time>
              </div>
              <h3>{post.title}</h3>
              <p>{post.body}</p>
              {onDeletePost && post.can_delete && (
                <button
                  type="button"
                  className="dashboard-link-btn"
                  onClick={() => onDeletePost(post.id)}
                >
                  Delete
                </button>
              )}
              {(post.replies || []).length > 0 && (
                <ul className="posting-board-replies">
                  {(post.replies || []).map((reply) => (
                    <li key={reply.id} className="posting-board-reply">
                      <div className="posting-board-item-header">
                        {reply.author ? (
                          <div className="posting-board-author">
                            {reply.author.profile_picture_url && (
                              <img
                                src={reply.author.profile_picture_url}
                                alt=""
                                className="posting-board-avatar"
                              />
                            )}
                            <div>
                              <strong>
                                {reply.author.display_name ||
                                  reply.author.username ||
                                  "Member"}
                              </strong>
                              {reply.author.username && (
                                <span className="posting-board-username">
                                  @{reply.author.username}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span />
                        )}
                        <time className="posting-board-date">
                          {formatDate(reply.created_at)}
                        </time>
                      </div>
                      <p>{reply.body}</p>
                      {onDeleteReply && reply.can_delete && (
                        <button
                          type="button"
                          className="dashboard-link-btn"
                          onClick={() => onDeleteReply(post.id, reply.id)}
                        >
                          Delete reply
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {canReply && onCreateReply && (
                <form
                  className="posting-board-reply-form"
                  onSubmit={(e) => handleReplySubmit(e, post.id)}
                >
                  <label htmlFor={`reply-${post.id}`}>Reply</label>
                  <textarea
                    id={`reply-${post.id}`}
                    rows={2}
                    value={replyBodies[post.id] || ""}
                    onChange={(e) =>
                      setReplyBodies((current) => ({
                        ...current,
                        [post.id]: e.target.value,
                      }))
                    }
                    required
                  />
                  {replyErrors[post.id] && (
                    <p className="dashboard-error">{replyErrors[post.id]}</p>
                  )}
                  <button
                    type="submit"
                    className="dashboard-btn"
                    disabled={submittingReplyId === post.id}
                  >
                    {submittingReplyId === post.id ? "Replying..." : "Reply"}
                  </button>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}

      {canPost && onCreatePost && (
        <form className="posting-board-form dashboard-form" onSubmit={handleSubmit}>
          <h3>New post</h3>
          <div className="dashboard-field">
            <label htmlFor="post-title">Title</label>
            <input
              id="post-title"
              value={postTitle}
              onChange={(e) => setPostTitle(e.target.value)}
              required
            />
          </div>
          <div className="dashboard-field">
            <label htmlFor="post-body">Message</label>
            <textarea
              id="post-body"
              rows={4}
              value={postBody}
              onChange={(e) => setPostBody(e.target.value)}
              required
            />
          </div>
          {formError && <p className="dashboard-error">{formError}</p>}
          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting}
          >
            {submitting ? "Posting..." : "Post"}
          </button>
        </form>
      )}
    </section>
  );
}
