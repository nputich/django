import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import { ensureValidSession } from "../auth";
import FavoriteStarButton from "../components/FavoriteStarButton";
import PostingBoard from "../components/PostingBoard";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/Board.css";
import "../styles/Relationships.css";
import "../styles/Dashboard.css";

function HubButton({ to, children, primary = false, onClick, disabled = false }) {
  const className = primary
    ? "dashboard-btn dashboard-btn--primary"
    : "dashboard-btn";
  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        disabled={disabled}
      >
        {children}
      </button>
    );
  }
  return (
    <Link to={to} className={className}>
      {children}
    </Link>
  );
}

export default function OrgHubPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState("");
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [favoriteBusy, setFavoriteBusy] = useState(false);
  const [favoriteError, setFavoriteError] = useState("");
  const signedIn = ensureValidSession();

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/hub/`)
      .then((res) => setOrg(res.data))
      .catch(() => setError("Organization not found."));
  }, [slug]);

  const handleFavorite = async () => {
    if (!ensureValidSession()) {
      navigate(`/?next=/org/${encodeURIComponent(slug)}/hub`);
      return;
    }
    if (!org) return;
    setFavoriteError("");
    setFavoriteBusy(true);
    try {
      if (org.is_favorite) {
        await api.delete(`/api/organizations/${slug}/favorite/`);
        setOrg({ ...org, is_favorite: false });
      } else {
        await api.post(`/api/organizations/${slug}/favorite/`);
        setOrg({ ...org, is_favorite: true });
      }
    } catch {
      setFavoriteError("Could not update favorites.");
    } finally {
      setFavoriteBusy(false);
    }
  };

  const handleJoin = async () => {
    setJoinError("");
    if (!ensureValidSession()) {
      navigate(`/?next=/org/${encodeURIComponent(slug)}/hub`);
      return;
    }
    setJoining(true);
    try {
      await api.post(`/api/organizations/${slug}/join/`);
      const res = await api.get(`/api/organizations/${slug}/hub/`);
      setOrg(res.data);
    } catch (err) {
      setJoinError(err.response?.data?.detail || "Could not join organization.");
    } finally {
      setJoining(false);
    }
  };

  if (error) {
    return (
      <div className="resource-page">
        <p>{error}</p>
        <HubButton to="/">Back to home</HubButton>
      </div>
    );
  }

  if (!org) return <div className="resource-page">Loading...</div>;

  const board = org.board;
  const showBoardPreview =
    org.has_board !== false &&
    board &&
    board.can_view !== false &&
    (board.hub_preview_count ?? 0) > 0;
  const rel = {
    parent: org.relationships?.parent || null,
    chapters: org.relationships?.chapters || [],
    partners: org.relationships?.partners || [],
    sponsors: org.relationships?.sponsors || [],
  };
  const hasRelationships =
    Boolean(rel.parent) ||
    rel.chapters.length > 0 ||
    rel.partners.length > 0 ||
    rel.sponsors.length > 0;

  return (
    <div className="resource-page">
      <div className="hub-top-actions">
        <HubButton to="/">← Back to home</HubButton>
      </div>
      <div className="hub-title-row">
        <h1>{org.name}</h1>
        <FavoriteStarButton
          favorited={Boolean(org.is_favorite)}
          onClick={handleFavorite}
          disabled={favoriteBusy}
          label={
            org.is_favorite
              ? `Remove ${org.name} from favorites`
              : `Add ${org.name} to favorites`
          }
        />
      </div>
      {(org.community_code || org.public_username) && (
        <p className="hub-communibetter-id">
          Community code:{" "}
          <strong>{org.community_code || org.public_username}</strong>
          {org.public_username ? (
            <span className="dashboard-meta">
              {" "}
              (also @{org.public_username})
            </span>
          ) : null}
        </p>
      )}
      {org.description && <p>{org.description}</p>}
      <button
        type="button"
        className="favorite-text-btn"
        onClick={handleFavorite}
        disabled={favoriteBusy}
      >
        {org.is_favorite ? "Remove from favorites" : "Add to favorites"}
      </button>
      {favoriteError && <p className="dashboard-error">{favoriteError}</p>}

      <section className="hub-section">
        <h2>Membership</h2>
        {org.is_member ? (
          <>
            <p>You are a member.</p>
            <div className="hub-button-row">
              {org.discovery_enabled && (
                <HubButton
                  to={`/dashboard/${org.slug}/map-search`}
                  primary
                >
                  Map Search
                </HubButton>
              )}
              <HubButton to={`/dashboard/${org.slug}`}>
                Open dashboard
              </HubButton>
            </div>
          </>
        ) : (
          <>
            <p>
              {signedIn
                ? "Join to access member features."
                : "Sign in, then join to access member features."}
            </p>
            {joinError && <p className="dashboard-error">{joinError}</p>}
            <div className="hub-button-row">
              <HubButton primary onClick={handleJoin} disabled={joining}>
                {joining
                  ? "Joining…"
                  : signedIn
                    ? "Join organization"
                    : "Sign in to join"}
              </HubButton>
            </div>
          </>
        )}
      </section>

      <section className="hub-section">
        <h2>Surveys</h2>
        {org.surveys.length === 0 ? (
          <p>No active surveys.</p>
        ) : (
          <ul className="hub-list hub-list--actions">
            {org.surveys.map((s) => (
              <li key={s.id}>
                <HubButton to={`/s/${s.id}`} primary>
                  {s.title}
                </HubButton>
                {s.description && <p>{s.description}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="hub-section">
        <h2>Meetings</h2>
        {org.meetings.length === 0 ? (
          <p>No upcoming meetings.</p>
        ) : (
          <ul className="hub-list hub-list--actions">
            {org.meetings.map((m) => (
              <li key={m.id}>
                <HubButton to={`/m/${m.id}`} primary>
                  {m.title}
                </HubButton>
                {m.description && <p>{m.description}</p>}
                <p className="resource-meta">
                  {m.status}
                  {m.scheduled_start_at &&
                    ` · ${new Date(m.scheduled_start_at).toLocaleString()}`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {showBoardPreview && (
        <section className="hub-section hub-board-preview">
          <PostingBoard
            title={board.title || org.name}
            posts={board.posts || []}
            canPost={false}
            canReply={false}
            emptyMessage="No posts on this board yet."
          />
          <div className="hub-button-row">
            <HubButton to={`/org/${org.slug}/board`}>View full board</HubButton>
          </div>
        </section>
      )}

      {org.has_board !== false && board && board.can_view === false && (
        <section className="hub-section">
          <h2>{board.title || "Posting board"}</h2>
          <p>This board is for organization members only.</p>
        </section>
      )}

      {hasRelationships && (
        <section className="hub-section">
          <h2>Affiliations</h2>
          <ul className="hub-list hub-list--actions relationship-public-list">
            {rel.parent && (
              <li>
                <span className="resource-meta">Chapter of</span>
                <HubButton to={`/org/${rel.parent.slug}`}>
                  {rel.parent.name}
                </HubButton>
              </li>
            )}
            {rel.chapters.length > 0 && (
              <li>
                <span className="resource-meta">Chapters &amp; members</span>
                <div className="hub-button-row">
                  {rel.chapters.map((o) => (
                    <HubButton key={o.slug} to={`/org/${o.slug}`}>
                      {o.name}
                    </HubButton>
                  ))}
                </div>
              </li>
            )}
            {rel.partners.length > 0 && (
              <li>
                <span className="resource-meta">Partners</span>
                <div className="hub-button-row">
                  {rel.partners.map((o) => (
                    <HubButton key={o.slug} to={`/org/${o.slug}`}>
                      {o.name}
                    </HubButton>
                  ))}
                </div>
              </li>
            )}
            {rel.sponsors.length > 0 && (
              <li>
                <span className="resource-meta">Sponsored by</span>
                <div className="hub-button-row">
                  {rel.sponsors.map((o) => (
                    <HubButton key={o.slug} to={`/org/${o.slug}`}>
                      {o.name}
                    </HubButton>
                  ))}
                </div>
              </li>
            )}
          </ul>
        </section>
      )}

      <section className="hub-section">
        <h2>Message this organization</h2>
        <p>Send a private message to the organization inbox.</p>
        <div className="hub-button-row">
          <HubButton
            to={`/dashboard/inbox?to_org=${encodeURIComponent(org.slug)}`}
            primary
          >
            Message {org.name}
          </HubButton>
        </div>
      </section>
    </div>
  );
}
