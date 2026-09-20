import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import PostingBoard from "../components/PostingBoard";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/Board.css";
import "../styles/Relationships.css";

export default function OrgHubPage() {
  const { slug } = useParams();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/hub/`)
      .then((res) => setOrg(res.data))
      .catch(() => setError("Organization not found."));
  }, [slug]);

  if (error) {
    return (
      <div className="resource-page">
        <p>{error}</p>
        <Link to="/">Back to home</Link>
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
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>{org.name}</h1>
      {org.description && <p>{org.description}</p>}

      <section className="hub-section">
        <h2>Surveys</h2>
        {org.surveys.length === 0 ? (
          <p>No active surveys.</p>
        ) : (
          <ul className="hub-list">
            {org.surveys.map((s) => (
              <li key={s.id}>
                <Link to={`/s/${s.id}`}>{s.title}</Link>
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
          <ul className="hub-list">
            {org.meetings.map((m) => (
              <li key={m.id}>
                <Link to={`/m/${m.id}`}>{m.title}</Link>
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
          <p className="hub-board-more">
            <Link to={`/org/${org.slug}/board`}>View full board</Link>
          </p>
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
          <ul className="hub-list hub-affiliations">
            {rel.parent && (
              <li>
                <span className="resource-meta">Part of</span>{" "}
                <Link to={`/org/${rel.parent.slug}`}>{rel.parent.name}</Link>
              </li>
            )}
            {rel.chapters.length > 0 && (
              <li>
                <span className="resource-meta">Chapters &amp; members</span>{" "}
                {rel.chapters.map((o, i) => (
                  <span key={o.slug}>
                    {i > 0 && ", "}
                    <Link to={`/org/${o.slug}`}>{o.name}</Link>
                  </span>
                ))}
              </li>
            )}
            {rel.partners.length > 0 && (
              <li>
                <span className="resource-meta">Partners</span>{" "}
                {rel.partners.map((o, i) => (
                  <span key={o.slug}>
                    {i > 0 && ", "}
                    <Link to={`/org/${o.slug}`}>{o.name}</Link>
                  </span>
                ))}
              </li>
            )}
            {rel.sponsors.length > 0 && (
              <li>
                <span className="resource-meta">Sponsored by</span>{" "}
                {rel.sponsors.map((o, i) => (
                  <span key={o.slug}>
                    {i > 0 && ", "}
                    <Link to={`/org/${o.slug}`}>{o.name}</Link>
                  </span>
                ))}
              </li>
            )}
          </ul>
        </section>
      )}

      <section className="hub-section">
        <h2>Message this organization</h2>
        <p>Send a private message to the organization inbox.</p>
        <Link to={`/dashboard/inbox?to_org=${encodeURIComponent(org.slug)}`}>
          Message {org.name}
        </Link>
      </section>
    </div>
  );
}
