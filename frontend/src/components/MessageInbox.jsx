import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import "../styles/Inbox.css";
import "../styles/PublicProfile.css";

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

function mailboxProfilePath(party) {
  if (!party) return null;
  if (party.organization_slug) {
    return `/org/${encodeURIComponent(party.organization_slug)}/hub`;
  }
  if (party.username) {
    return `/u/${encodeURIComponent(party.username)}`;
  }
  return null;
}

function MailboxLink({ party, children, className = "inbox-party-link" }) {
  const path = mailboxProfilePath(party);
  if (!path) {
    return <span>{children || party?.display_name || "Unknown"}</span>;
  }
  return (
    <Link
      to={path}
      className={className}
      onClick={(e) => e.stopPropagation()}
    >
      {children || party.display_name || party.username}
    </Link>
  );
}

function CounterpartyLinks({ item }) {
  const people = item?.counterparties || [];
  if (!people.length) return "Conversation";
  return people.map((party, index) => (
    <span key={party.id || party.username || party.organization_slug || index}>
      {index > 0 ? ", " : null}
      <MailboxLink party={party} />
      {party.username ? (
        <span className="inbox-party-username">@{party.username}</span>
      ) : null}
    </span>
  ));
}

/**
 * Shared inbox UI for personal and organization mailboxes.
 *
 * @param {string} apiBase e.g. "/api/me/inbox" or "/api/organizations/slug/inbox"
 * @param {"personal"|"organization"} mailboxKind
 * @param {object} [composeDefaults] optional { to_organization_slug, to_username, subject }
 */
export default function MessageInbox({
  apiBase,
  mailboxKind = "personal",
  composeDefaults = null,
  title = "Inbox",
}) {
  const [folder, setFolder] = useState("primary");
  const [summary, setSummary] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [thread, setThread] = useState(null);
  const [editingDraft, setEditingDraft] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [composeOpen, setComposeOpen] = useState(Boolean(composeDefaults));
  const [compose, setCompose] = useState({
    subject: composeDefaults?.subject || "",
    body: "",
    to_username: composeDefaults?.to_username || "",
    to_organization_slug: composeDefaults?.to_organization_slug || "",
  });
  const [replyBody, setReplyBody] = useState("");
  const [busy, setBusy] = useState(false);

  const recipientMode = useMemo(() => {
    if (mailboxKind === "organization") return "user";
    if (compose.to_organization_slug) return "org";
    return composeDefaults?.to_organization_slug ? "org" : "user";
  }, [mailboxKind, compose.to_organization_slug, composeDefaults]);

  const loadFolder = useCallback(
    async ({ quiet = false } = {}) => {
      if (!quiet) {
        setLoading(true);
      }
      setError("");
      try {
        if (folder === "drafts") {
          const res = await api.get(`${apiBase}/drafts/`);
          setSummary(res.data);
          setDrafts(res.data.drafts || []);
          setConversations([]);
        } else {
          const res = await api.get(`${apiBase}/`, { params: { folder } });
          setSummary(res.data);
          setConversations(res.data.conversations || []);
          setDrafts([]);
        }
      } catch (err) {
        setError(err.response?.data?.detail || "Could not load inbox.");
      } finally {
        if (!quiet) {
          setLoading(false);
        }
      }
    },
    [apiBase, folder]
  );

  useEffect(() => {
    loadFolder();
  }, [loadFolder]);

  const openConversation = async (id) => {
    setError("");
    setEditingDraft(null);
    setComposeOpen(false);
    setActiveId(id);
    try {
      const res = await api.get(`${apiBase}/conversations/${id}/`);
      setThread(res.data);
      setReplyBody("");
      // Quiet refresh: keep conversation visible; only drop bold unread state.
      await loadFolder({ quiet: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not open conversation.");
    }
  };

  const openDraft = (draft) => {
    setThread(null);
    setActiveId(null);
    setEditingDraft(draft);
    setCompose({
      subject: draft.subject || "",
      body: draft.body || "",
      to_username: draft.to?.username || "",
      to_organization_slug: draft.to?.organization_slug || "",
    });
    setComposeOpen(true);
  };

  const handleSaveDraft = async () => {
    setBusy(true);
    setError("");
    try {
      const payload = {
        subject: compose.subject,
        body: compose.body,
      };
      if (recipientMode === "org") {
        payload.to_organization_slug = compose.to_organization_slug.trim();
      } else {
        payload.to_username = compose.to_username.trim();
      }
      if (editingDraft?.id) {
        const res = await api.patch(
          `${apiBase}/drafts/${editingDraft.id}/`,
          payload
        );
        setEditingDraft(res.data);
      } else {
        const res = await api.post(`${apiBase}/drafts/`, payload);
        setEditingDraft(res.data);
      }
      setFolder("drafts");
      await loadFolder();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.to_username?.[0] ||
          "Could not save draft."
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSendDraft = async () => {
    setBusy(true);
    setError("");
    try {
      let draftId = editingDraft?.id;
      if (!draftId) {
        const payload = {
          subject: compose.subject,
          body: compose.body,
        };
        if (recipientMode === "org") {
          payload.to_organization_slug = compose.to_organization_slug.trim();
        } else {
          payload.to_username = compose.to_username.trim();
        }
        const created = await api.post(`${apiBase}/drafts/`, payload);
        draftId = created.data.id;
      } else {
        await api.patch(`${apiBase}/drafts/${draftId}/`, {
          subject: compose.subject,
          body: compose.body,
          ...(recipientMode === "org"
            ? { to_organization_slug: compose.to_organization_slug.trim() }
            : { to_username: compose.to_username.trim() }),
        });
      }
      const sent = await api.post(`${apiBase}/drafts/${draftId}/send/`);
      setComposeOpen(false);
      setEditingDraft(null);
      setCompose({ subject: "", body: "", to_username: "", to_organization_slug: "" });
      setFolder("primary");
      await openConversation(sent.data.id);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not send message.");
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteDraft = async (id) => {
    if (!window.confirm("Delete this draft?")) return;
    await api.delete(`${apiBase}/drafts/${id}/`);
    if (editingDraft?.id === id) {
      setEditingDraft(null);
      setComposeOpen(false);
    }
    await loadFolder();
  };

  const handleReply = async ({ send }) => {
    if (!thread?.id || !replyBody.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.post(`${apiBase}/conversations/${thread.id}/reply/`, {
        body: replyBody,
        send,
      });
      if (send) {
        setThread(res.data);
        setReplyBody("");
        await loadFolder();
      } else {
        setFolder("drafts");
        setReplyBody("");
        await loadFolder();
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Could not save reply.");
    } finally {
      setBusy(false);
    }
  };

  const handleAccept = async (id) => {
    await api.post(`${apiBase}/conversations/${id}/accept/`);
    // Stay with the thread — move UI to Inbox so it does not look deleted.
    setFolder("primary");
    setActiveId(id);
    const res = await api.get(`${apiBase}/conversations/${id}/`);
    setThread(res.data);
  };

  const handleDecline = async (id) => {
    if (!window.confirm("Decline and archive this message request?")) return;
    await api.post(`${apiBase}/conversations/${id}/decline/`);
    setThread(null);
    setActiveId(null);
    await loadFolder({ quiet: true });
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this conversation from your inbox?")) return;
    setBusy(true);
    try {
      await api.delete(`${apiBase}/conversations/${id}/`);
      setThread(null);
      setActiveId(null);
      await loadFolder({ quiet: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not delete conversation.");
    } finally {
      setBusy(false);
    }
  };

  const handleBan = async (id) => {
    if (
      !window.confirm(
        "Ban this user? They will no longer be able to see or message you, and shared conversations will be removed."
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await api.post(`${apiBase}/conversations/${id}/ban/`);
      setThread(null);
      setActiveId(null);
      await loadFolder({ quiet: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not ban user.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="inbox">
      <div className="inbox-header">
        <h2>{title}</h2>
        <button
          type="button"
          className="dashboard-btn dashboard-btn--primary"
          onClick={() => {
            setComposeOpen(true);
            setEditingDraft(null);
            setThread(null);
            setActiveId(null);
            setCompose({
              subject: composeDefaults?.subject || "",
              body: "",
              to_username: composeDefaults?.to_username || "",
              to_organization_slug: composeDefaults?.to_organization_slug || "",
            });
          }}
        >
          New message
        </button>
      </div>

      <div className="inbox-folders" role="tablist" aria-label="Inbox folders">
        <button
          type="button"
          className={folder === "primary" ? "inbox-folder is-active" : "inbox-folder"}
          onClick={() => {
            setFolder("primary");
            setThread(null);
            setActiveId(null);
          }}
        >
          Inbox
          {summary?.primary_unread ? (
            <span className="inbox-badge">{summary.primary_unread}</span>
          ) : null}
        </button>
        <button
          type="button"
          className={folder === "unknown" ? "inbox-folder is-active" : "inbox-folder"}
          onClick={() => {
            setFolder("unknown");
            setThread(null);
            setActiveId(null);
          }}
        >
          Unknown
          {summary?.unknown_unread ? (
            <span className="inbox-badge">{summary.unknown_unread}</span>
          ) : null}
        </button>
        <button
          type="button"
          className={folder === "drafts" ? "inbox-folder is-active" : "inbox-folder"}
          onClick={() => {
            setFolder("drafts");
            setThread(null);
            setActiveId(null);
          }}
        >
          Drafts
          {summary?.drafts_count ? (
            <span className="inbox-badge">{summary.drafts_count}</span>
          ) : null}
        </button>
      </div>

      {error && <p className="dashboard-error">{error}</p>}

      <div className="inbox-layout">
        <div className="inbox-list-pane">
          {loading && <p className="dashboard-empty">Loading…</p>}
          {!loading && folder === "drafts" && drafts.length === 0 && (
            <p className="dashboard-empty">No drafts.</p>
          )}
          {!loading && folder !== "drafts" && conversations.length === 0 && (
            <p className="dashboard-empty">
              {folder === "unknown"
                ? "No messages from people you don’t know."
                : "No conversations yet."}
            </p>
          )}
          {folder === "drafts"
            ? drafts.map((draft) => (
                <button
                  key={draft.id}
                  type="button"
                  className={
                    editingDraft?.id === draft.id
                      ? "inbox-list-item is-active"
                      : "inbox-list-item"
                  }
                  onClick={() => openDraft(draft)}
                >
                  <strong>{draft.subject || "(No subject)"}</strong>
                  <span>
                    {draft.to?.display_name
                      ? `To ${draft.to.display_name}`
                      : "No recipient yet"}
                  </span>
                  <time>{formatDate(draft.updated_at)}</time>
                </button>
              ))
            : conversations.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={
                    activeId === item.id
                      ? `inbox-list-item is-active${item.unread ? " is-unread" : ""}`
                      : `inbox-list-item${item.unread ? " is-unread" : ""}`
                  }
                  onClick={() => openConversation(item.id)}
                >
                  <strong>{item.subject || <CounterpartyLinks item={item} />}</strong>
                  <span>
                    <CounterpartyLinks item={item} />
                  </span>
                  <span className="inbox-preview">{item.preview}</span>
                  <time>{formatDate(item.last_message_at || item.updated_at)}</time>
                </button>
              ))}
        </div>

        <div className="inbox-detail-pane">
          {composeOpen && (
            <div className="inbox-compose">
              <h3>{editingDraft ? "Edit draft" : "New message"}</h3>
              {recipientMode === "org" ? (
                <label>
                  Organization slug
                  <input
                    value={compose.to_organization_slug}
                    onChange={(e) =>
                      setCompose((c) => ({
                        ...c,
                        to_organization_slug: e.target.value,
                      }))
                    }
                    placeholder="organization-slug"
                  />
                </label>
              ) : (
                <label>
                  To username
                  <input
                    value={compose.to_username}
                    onChange={(e) =>
                      setCompose((c) => ({ ...c, to_username: e.target.value }))
                    }
                    placeholder="username"
                  />
                </label>
              )}
              <label>
                Subject
                <input
                  value={compose.subject}
                  onChange={(e) =>
                    setCompose((c) => ({ ...c, subject: e.target.value }))
                  }
                />
              </label>
              <label>
                Message
                <textarea
                  rows={6}
                  value={compose.body}
                  onChange={(e) =>
                    setCompose((c) => ({ ...c, body: e.target.value }))
                  }
                />
              </label>
              <div className="inbox-actions">
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={handleSaveDraft}
                >
                  Save draft
                </button>
                <button
                  type="button"
                  className="dashboard-btn dashboard-btn--primary"
                  disabled={busy}
                  onClick={handleSendDraft}
                >
                  Send
                </button>
                {editingDraft && (
                  <button
                    type="button"
                    className="dashboard-link-btn"
                    onClick={() => handleDeleteDraft(editingDraft.id)}
                  >
                    Delete draft
                  </button>
                )}
                <button
                  type="button"
                  className="dashboard-link-btn"
                  onClick={() => {
                    setComposeOpen(false);
                    setEditingDraft(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {!composeOpen && !thread && (
            <p className="dashboard-empty">Select a conversation or start a new message.</p>
          )}

          {!composeOpen && thread && (
            <div className="inbox-thread">
              <div className="inbox-thread-header">
                <div>
                  <h3>{thread.subject || "Conversation"}</h3>
                  <p className="dashboard-meta">
                    <CounterpartyLinks item={thread} />
                  </p>
                </div>
                <div className="inbox-actions">
                  {thread.folder === "unknown" && (
                    <>
                      <button
                        type="button"
                        className="dashboard-btn dashboard-btn--primary"
                        onClick={() => handleAccept(thread.id)}
                      >
                        Accept
                      </button>
                      <button
                        type="button"
                        className="dashboard-btn"
                        onClick={() => handleDecline(thread.id)}
                      >
                        Decline
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className="dashboard-btn"
                    disabled={busy}
                    onClick={() => handleDelete(thread.id)}
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn inbox-ban-btn"
                    disabled={busy}
                    onClick={() => handleBan(thread.id)}
                  >
                    Ban user
                  </button>
                </div>
              </div>
              <ul className="inbox-messages">
                {(thread.messages || []).map((msg) => (
                  <li key={msg.id} className="inbox-message">
                    <div className="inbox-message-meta">
                      <span>
                        <MailboxLink party={msg.sender}>
                          {msg.sender?.display_name || msg.sender?.username}
                        </MailboxLink>
                        {msg.sender?.username ? (
                          <span className="inbox-party-username">
                            @{msg.sender.username}
                          </span>
                        ) : msg.sender?.organization_slug ? (
                          <span className="inbox-party-username">
                            /{msg.sender.organization_slug}
                          </span>
                        ) : null}
                      </span>
                      <time>{formatDate(msg.sent_at)}</time>
                    </div>
                    <p>{msg.body}</p>
                  </li>
                ))}
              </ul>
              <div className="inbox-reply">
                <textarea
                  rows={4}
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder="Write a reply…"
                />
                <div className="inbox-actions">
                  <button
                    type="button"
                    className="dashboard-btn"
                    disabled={busy || !replyBody.trim()}
                    onClick={() => handleReply({ send: false })}
                  >
                    Save draft
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--primary"
                    disabled={busy || !replyBody.trim()}
                    onClick={() => handleReply({ send: true })}
                  >
                    Send reply
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
