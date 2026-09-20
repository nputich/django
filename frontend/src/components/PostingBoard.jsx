import { useEffect, useMemo, useRef, useState } from "react";
import "../styles/Board.css";

const POST_TYPES = [
  { id: "post", label: "Post" },
  { id: "question", label: "Question" },
  { id: "poll", label: "Poll" },
  { id: "event", label: "Event" },
];

const TYPE_LABELS = {
  question: "QUESTION",
  poll: "POLL",
  event: "EVENT",
};

const BODY_LIMIT = 220;

function formatRelativeTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const sec = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (sec < 60) return "Just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatEventWhen(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatEventDay(iso) {
  if (!iso) return { month: "", day: "" };
  const d = new Date(iso);
  return {
    month: d.toLocaleString(undefined, { month: "short" }).toUpperCase(),
    day: String(d.getDate()),
  };
}

function authorInitials(author) {
  const name = author?.display_name || author?.username || "?";
  const parts = String(name).trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function AuthorAvatar({ author, size = "md" }) {
  if (author?.profile_picture_url) {
    return (
      <img
        src={author.profile_picture_url}
        alt=""
        className={`wall-avatar wall-avatar--${size}`}
      />
    );
  }
  return (
    <span
      className={`wall-avatar wall-avatar--${size} wall-avatar--fallback`}
      aria-hidden
    >
      {authorInitials(author)}
    </span>
  );
}

function TruncatedBody({ text }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;
  const needsTruncate = text.length > BODY_LIMIT;
  const shown =
    !needsTruncate || expanded
      ? text
      : `${text.slice(0, BODY_LIMIT).trimEnd()}…`;
  return (
    <div className="wall-body">
      <p>{shown}</p>
      {needsTruncate && (
        <button
          type="button"
          className="wall-see-more"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "See less" : "See more"}
        </button>
      )}
    </div>
  );
}

function PollBlock({ poll, onVote }) {
  if (!poll) return null;
  const showResults = poll.viewer_option_id != null;
  return (
    <div className="wall-poll">
      <ul className="wall-poll-options">
        {poll.options.map((opt) => {
          const selected = poll.viewer_option_id === opt.id;
          return (
            <li key={opt.id}>
              <button
                type="button"
                className={`wall-poll-option${
                  selected ? " wall-poll-option--selected" : ""
                }`}
                disabled={!onVote}
                onClick={() => onVote?.(opt.id)}
              >
                {showResults && (
                  <span
                    className="wall-poll-option-bar"
                    style={{ width: `${opt.percent || 0}%` }}
                  />
                )}
                <span className="wall-poll-option-label">{opt.text}</span>
                {showResults && (
                  <span className="wall-poll-option-pct">{opt.percent || 0}%</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="wall-poll-meta">
        {poll.total_votes} {poll.total_votes === 1 ? "response" : "responses"}
      </p>
    </div>
  );
}

function EventBlock({ post }) {
  const day = formatEventDay(post.event_starts_at);
  return (
    <div className="wall-event">
      <div className="wall-event-date" aria-hidden>
        <span className="wall-event-month">{day.month}</span>
        <span className="wall-event-day">{day.day}</span>
      </div>
      <div className="wall-event-copy">
        <strong>{post.title}</strong>
        <span>{formatEventWhen(post.event_starts_at)}</span>
        {post.event_location ? <span>{post.event_location}</span> : null}
      </div>
    </div>
  );
}

function formatMeetingWhenLine(meeting) {
  const parts = [];
  if (meeting.scheduled_start_at) {
    const d = new Date(meeting.scheduled_start_at);
    const weekday = d.toLocaleString(undefined, { weekday: "long" });
    const time = d.toLocaleString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    parts.push(`${weekday} · ${time}`);
  }
  if (meeting.location) parts.push(meeting.location);
  return parts.join(" · ");
}

function RsvpControl({ meeting, onRsvp, busy }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const label =
    meeting.my_rsvp === "going"
      ? "Going"
      : meeting.my_rsvp === "pending"
        ? "Pending"
        : "Going";

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!meeting.actions?.can_rsvp || !onRsvp) return null;

  return (
    <div className="wall-meeting-rsvp" ref={ref}>
      <button
        type="button"
        className={`wall-meeting-action${meeting.my_rsvp ? " is-selected" : ""}`}
        aria-expanded={open}
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
      >
        {label} ▾
      </button>
      {open && (
        <div className="wall-meeting-rsvp-menu" role="menu">
          <button
            type="button"
            role="menuitem"
            disabled={busy}
            onClick={async () => {
              setOpen(false);
              await onRsvp(meeting.id, "going");
            }}
          >
            Going
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={busy}
            onClick={async () => {
              setOpen(false);
              await onRsvp(meeting.id, "pending");
            }}
          >
            Pending
          </button>
          {meeting.my_rsvp && (
            <button
              type="button"
              role="menuitem"
              disabled={busy}
              onClick={async () => {
                setOpen(false);
                await onRsvp(meeting.id, "");
              }}
            >
              Remove response
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function MeetingWallBlock({ meeting, onRsvp }) {
  const [busy, setBusy] = useState(false);
  if (!meeting) return null;

  const handleRsvp = async (meetingId, status) => {
    if (!onRsvp) return;
    setBusy(true);
    try {
      await onRsvp(meetingId, status);
    } finally {
      setBusy(false);
    }
  };

  const phase = meeting.phase || "upcoming";
  const whenLine = formatMeetingWhenLine(meeting);
  const totals = meeting.totals;

  return (
    <div className={`wall-meeting wall-meeting--${phase}`}>
      {phase === "upcoming" && (
        <>
          <span className="wall-meeting-badge">COMMUNITY MEETING</span>
          <h3 className="wall-meeting-title">{meeting.title}</h3>
          {whenLine ? <p className="wall-meeting-when">{whenLine}</p> : null}
          <div className="wall-meeting-actions">
            <RsvpControl meeting={meeting} onRsvp={handleRsvp} busy={busy} />
            <a className="wall-meeting-action" href={meeting.paths?.details}>
              View Details
            </a>
          </div>
        </>
      )}

      {phase === "in_progress" && (
        <>
          <span className="wall-meeting-badge wall-meeting-badge--live">
            <span className="wall-meeting-live-dot" aria-hidden />
            MEETING IN PROGRESS
          </span>
          <h3 className="wall-meeting-title">{meeting.title}</h3>
          <div className="wall-meeting-actions">
            <a
              className="wall-meeting-action wall-meeting-action--primary"
              href={meeting.paths?.join}
            >
              Join Meeting
            </a>
          </div>
        </>
      )}

      {phase === "complete" && (
        <>
          <span className="wall-meeting-badge">MEETING COMPLETE</span>
          <h3 className="wall-meeting-title">{meeting.title}</h3>
          {totals ? (
            <p className="wall-meeting-when">
              {totals.participant_count}{" "}
              {totals.participant_count === 1 ? "participant" : "participants"}
              {" · "}
              {totals.response_count}{" "}
              {totals.response_count === 1 ? "response" : "responses"}
            </p>
          ) : null}
          <div className="wall-meeting-actions">
            {meeting.actions?.can_view_results ? (
              <a className="wall-meeting-action" href={meeting.paths?.results}>
                View Results
              </a>
            ) : null}
            {meeting.actions?.can_read_summary ? (
              <a className="wall-meeting-action" href={meeting.paths?.summary}>
                Read Summary
              </a>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function WallPostCard({
  post,
  canReply,
  onCreateReply,
  onDeletePost,
  onDeleteReply,
  onVotePoll,
  onMeetingRsvp,
  visibilityLabel,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [replyBody, setReplyBody] = useState("");
  const [replyError, setReplyError] = useState("");
  const [replySubmitting, setReplySubmitting] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDoc = (e) => {
      if (!menuRef.current?.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const typeLabel = post.type_label || TYPE_LABELS[post.post_type] || "";
  const authorName =
    post.author?.display_name || post.author?.username || "Member";

  const handleShare = async () => {
    const url = `${window.location.origin}${window.location.pathname}#wall-post-${post.id}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      // ignore
    }
  };

  const handleReply = async (e) => {
    e.preventDefault();
    if (!onCreateReply || !replyBody.trim()) return;
    setReplySubmitting(true);
    setReplyError("");
    try {
      await onCreateReply(post.id, { body: replyBody.trim() });
      setReplyBody("");
    } catch (err) {
      setReplyError(err.response?.data?.detail || "Could not save comment.");
    } finally {
      setReplySubmitting(false);
    }
  };

  return (
    <article id={`wall-post-${post.id}`} className="wall-card">
      <header className="wall-card-header">
        <AuthorAvatar author={post.author} />
        <div className="wall-card-meta">
          <strong className="wall-card-name">{authorName}</strong>
          <span className="wall-card-sub">
            {formatRelativeTime(post.created_at)}
            {visibilityLabel ? ` · ${visibilityLabel}` : ""}
          </span>
        </div>
        <div className="wall-card-menu" ref={menuRef}>
          <button
            type="button"
            className="wall-card-menu-btn"
            aria-label="Post options"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            ···
          </button>
          {menuOpen && (
            <div className="wall-card-menu-panel" role="menu">
              {onDeletePost && post.can_delete && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    onDeletePost(post.id);
                  }}
                >
                  Delete
                </button>
              )}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  handleShare();
                }}
              >
                Copy link
              </button>
            </div>
          )}
        </div>
      </header>

      {typeLabel ? <span className="wall-type-label">{typeLabel}</span> : null}

      {post.post_type === "meeting" && (
        <MeetingWallBlock meeting={post.meeting} onRsvp={onMeetingRsvp} />
      )}

      {post.post_type === "event" && <EventBlock post={post} />}

      {post.post_type === "question" && (
        <div className="wall-question">
          <TruncatedBody text={post.body} />
          {(canReply || onCreateReply) && (
            <button
              type="button"
              className="wall-question-cta"
              onClick={() => setShowComments(true)}
            >
              Share your answer
            </button>
          )}
        </div>
      )}

      {post.post_type === "poll" && (
        <>
          <TruncatedBody text={post.body} />
          <PollBlock
            poll={post.poll}
            onVote={
              onVotePoll ? (optionId) => onVotePoll(post.id, optionId) : undefined
            }
          />
        </>
      )}

      {post.post_type === "post" && (
        <>
          {post.title ? (
            <h3 className="wall-optional-title">{post.title}</h3>
          ) : null}
          <TruncatedBody text={post.body} />
        </>
      )}

      {post.post_type === "event" && post.body ? (
        <TruncatedBody text={post.body} />
      ) : null}

      <footer className="wall-card-footer">
        <button type="button" className="wall-action" disabled title="Coming soon">
          Like
        </button>
        <button
          type="button"
          className="wall-action"
          onClick={() => setShowComments((v) => !v)}
        >
          Comment
          {(post.replies || []).length > 0 ? ` (${post.replies.length})` : ""}
        </button>
        <button type="button" className="wall-action" onClick={handleShare}>
          Share
        </button>
      </footer>

      {showComments && (
        <div className="wall-comments">
          {(post.replies || []).length > 0 && (
            <ul className="wall-comment-list">
              {(post.replies || []).map((reply) => (
                <li key={reply.id} className="wall-comment">
                  <AuthorAvatar author={reply.author} size="sm" />
                  <div className="wall-comment-body">
                    <div className="wall-comment-head">
                      <strong>
                        {reply.author?.display_name ||
                          reply.author?.username ||
                          "Member"}
                      </strong>
                      <time>{formatRelativeTime(reply.created_at)}</time>
                    </div>
                    <p>{reply.body}</p>
                    {onDeleteReply && reply.can_delete && (
                      <button
                        type="button"
                        className="wall-comment-delete"
                        onClick={() => onDeleteReply(post.id, reply.id)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {canReply && onCreateReply && (
            <form className="wall-comment-form" onSubmit={handleReply}>
              <textarea
                rows={2}
                placeholder={
                  post.post_type === "question"
                    ? "Share your answer…"
                    : "Write a comment…"
                }
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                required
              />
              {replyError && <p className="dashboard-error">{replyError}</p>}
              <button
                type="submit"
                className="dashboard-btn dashboard-btn--primary"
                disabled={replySubmitting}
              >
                {replySubmitting ? "Posting…" : "Comment"}
              </button>
            </form>
          )}
          {!canReply && !(post.replies || []).length && (
            <p className="wall-comments-empty">No comments yet.</p>
          )}
        </div>
      )}
    </article>
  );
}

function WallComposer({ canPost, onCreatePost, composerAvatar }) {
  const [expanded, setExpanded] = useState(false);
  const [postType, setPostType] = useState("post");
  const [body, setBody] = useState("");
  const [title, setTitle] = useState("");
  const [pollOptions, setPollOptions] = useState(["", ""]);
  const [eventStartsAt, setEventStartsAt] = useState("");
  const [eventEndsAt, setEventEndsAt] = useState("");
  const [eventLocation, setEventLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [moreOpen, setMoreOpen] = useState(false);

  const reset = () => {
    setBody("");
    setTitle("");
    setPollOptions(["", ""]);
    setEventStartsAt("");
    setEventEndsAt("");
    setEventLocation("");
    setError("");
    setPostType("post");
    setExpanded(false);
    setMoreOpen(false);
  };

  const selectType = (id) => {
    setPostType(id);
    setExpanded(true);
    setMoreOpen(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canPost || !onCreatePost) return;
    setSubmitting(true);
    setError("");
    const payload = {
      post_type: postType,
      body: body.trim(),
      title: title.trim(),
    };
    if (postType === "poll") {
      payload.poll_options = pollOptions.map((o) => o.trim()).filter(Boolean);
    }
    if (postType === "event") {
      payload.event_starts_at = eventStartsAt
        ? new Date(eventStartsAt).toISOString()
        : "";
      payload.event_ends_at = eventEndsAt
        ? new Date(eventEndsAt).toISOString()
        : "";
      payload.event_location = eventLocation.trim();
    }
    try {
      await onCreatePost(payload);
      reset();
    } catch (err) {
      const data = err.response?.data;
      const detail =
        data?.detail ||
        data?.body?.[0] ||
        data?.title?.[0] ||
        data?.poll_options?.[0] ||
        data?.event_starts_at?.[0] ||
        "Could not publish.";
      setError(String(detail));
    } finally {
      setSubmitting(false);
    }
  };

  if (!canPost || !onCreatePost) return null;

  return (
    <div className={`wall-composer${expanded ? " wall-composer--open" : ""}`}>
      {!expanded ? (
        <>
          <button
            type="button"
            className="wall-composer-collapsed"
            onClick={() => setExpanded(true)}
          >
            <AuthorAvatar author={composerAvatar} />
            <span>Share something with your community…</span>
          </button>
          <div className="wall-composer-types">
            {POST_TYPES.map((t) => (
              <button
                key={t.id}
                type="button"
                className="wall-composer-type"
                onClick={() => selectType(t.id)}
              >
                {t.label}
              </button>
            ))}
            <div className="wall-composer-more-wrap">
              <button
                type="button"
                className="wall-composer-type"
                onClick={() => setMoreOpen((v) => !v)}
              >
                More
              </button>
              {moreOpen && (
                <div className="wall-composer-more-menu">
                  <span className="wall-composer-more-soon">Photo — soon</span>
                  <span className="wall-composer-more-soon">Link — soon</span>
                  <span className="wall-composer-more-soon">Survey — soon</span>
                  <span className="wall-composer-more-soon">
                    Meetings are created from the dashboard
                  </span>
                  <span className="wall-composer-more-soon">Results — soon</span>
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <form className="wall-composer-form" onSubmit={handleSubmit}>
          <div className="wall-composer-types">
            {POST_TYPES.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`wall-composer-type${
                  postType === t.id ? " wall-composer-type--active" : ""
                }`}
                onClick={() => setPostType(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {postType === "event" && (
            <>
              <input
                className="wall-input"
                placeholder="Event title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
              <div className="wall-composer-row">
                <label>
                  Starts
                  <input
                    type="datetime-local"
                    className="wall-input"
                    value={eventStartsAt}
                    onChange={(e) => setEventStartsAt(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Ends
                  <input
                    type="datetime-local"
                    className="wall-input"
                    value={eventEndsAt}
                    onChange={(e) => setEventEndsAt(e.target.value)}
                  />
                </label>
              </div>
              <input
                className="wall-input"
                placeholder="Location"
                value={eventLocation}
                onChange={(e) => setEventLocation(e.target.value)}
              />
              <textarea
                className="wall-input"
                rows={3}
                placeholder="Add details (optional)"
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </>
          )}

          {postType === "poll" && (
            <>
              <textarea
                className="wall-input"
                rows={2}
                placeholder="Ask a poll question…"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                required
              />
              {pollOptions.map((opt, idx) => (
                <input
                  key={`poll-opt-${idx}`}
                  className="wall-input"
                  placeholder={`Option ${idx + 1}`}
                  value={opt}
                  onChange={(e) => {
                    const next = [...pollOptions];
                    next[idx] = e.target.value;
                    setPollOptions(next);
                  }}
                />
              ))}
              {pollOptions.length < 8 && (
                <button
                  type="button"
                  className="wall-link-btn"
                  onClick={() => setPollOptions((o) => [...o, ""])}
                >
                  + Add option
                </button>
              )}
            </>
          )}

          {(postType === "post" || postType === "question") && (
            <textarea
              className="wall-input"
              rows={3}
              placeholder={
                postType === "question"
                  ? "What do you want to ask your community?"
                  : "Share something with your community…"
              }
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
          )}

          {error && <p className="dashboard-error">{error}</p>}

          <div className="wall-composer-actions">
            <button type="button" className="dashboard-btn" onClick={reset}>
              Cancel
            </button>
            <button
              type="submit"
              className="dashboard-btn dashboard-btn--primary"
              disabled={submitting}
            >
              {submitting ? "Posting…" : "Post"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function PostingBoard({
  title,
  postingModeLabel,
  postingMode,
  posts = [],
  canPost,
  canReply,
  readOnlyMessage,
  onCreatePost,
  onCreateReply,
  onDeletePost,
  onDeleteReply,
  onVotePoll,
  onMeetingRsvp,
  emptyMessage = "No posts yet.",
  composerAvatar = null,
  visibilityLabel,
}) {
  const feedVisibility = useMemo(
    () => visibilityLabel || postingModeLabel || postingMode || "",
    [visibilityLabel, postingModeLabel, postingMode]
  );

  return (
    <section className="wall">
      <div className="wall-header">
        <h2>{title || "Community wall"}</h2>
        {postingModeLabel && (
          <span className="wall-mode-pill">{postingModeLabel}</span>
        )}
      </div>

      {!canPost && readOnlyMessage && (
        <p className="wall-readonly">{readOnlyMessage}</p>
      )}

      <div className="wall-feed">
        <WallComposer
          canPost={canPost}
          onCreatePost={onCreatePost}
          composerAvatar={composerAvatar}
        />

        {posts.length === 0 ? (
          <p className="dashboard-empty">{emptyMessage}</p>
        ) : (
          posts.map((post) => (
            <WallPostCard
              key={post.id}
              post={post}
              canReply={canReply}
              onCreateReply={onCreateReply}
              onDeletePost={onDeletePost}
              onDeleteReply={onDeleteReply}
              onVotePoll={onVotePoll}
              onMeetingRsvp={onMeetingRsvp}
              visibilityLabel={feedVisibility}
            />
          ))
        )}
      </div>
    </section>
  );
}
