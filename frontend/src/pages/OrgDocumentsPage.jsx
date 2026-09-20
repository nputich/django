import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/Tags.css";

function formatBytes(n) {
  if (!n && n !== 0) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function OrgSearch({ excludeSlug, onPick }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .get("/api/organizations/lookup/", {
          params: { q: q.trim(), exclude: excludeSlug },
        })
        .then((res) => setResults(res.data.results || []))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(handle);
  }, [q, excludeSlug]);

  return (
    <div className="tag-picker">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search organizations…"
        aria-label="Search organizations"
      />
      {results.length > 0 && (
        <div className="tag-picker-menu">
          {results.map((o) => (
            <button
              key={o.slug}
              type="button"
              className="tag-picker-create"
              onClick={() => {
                onPick(o);
                setQ("");
                setResults([]);
              }}
            >
              {o.name} <span className="dashboard-meta">/{o.slug}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function UserSearch({ onPick }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .get("/api/users/lookup/", { params: { q: q.trim() } })
        .then((res) => setResults(res.data.results || []))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(handle);
  }, [q]);

  return (
    <div className="tag-picker">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search people by name or username…"
        aria-label="Search people"
      />
      {results.length > 0 && (
        <div className="tag-picker-menu">
          {results.map((u) => (
            <button
              key={u.id}
              type="button"
              className="tag-picker-create"
              onClick={() => {
                onPick(u);
                setQ("");
                setResults([]);
              }}
            >
              {u.display_name}{" "}
              <span className="dashboard-meta">@{u.username}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function OrgDocumentsPage() {
  const { slug } = useParams();
  const [orgName, setOrgName] = useState(slug);
  const [limits, setLimits] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [lists, setLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [visibility, setVisibility] = useState("private");
  const [uploading, setUploading] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [newListName, setNewListName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [dashRes, docsRes, listsRes] = await Promise.all([
        api.get(`/api/organizations/${slug}/dashboard/`),
        api.get(`/api/organizations/${slug}/documents/`),
        api.get(`/api/organizations/${slug}/documents/share-lists/`),
      ]);
      setOrgName(dashRes.data.name || slug);
      setLimits(docsRes.data.limits);
      setDocuments(docsRes.data.documents || []);
      setLists(listsRes.data.lists || []);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load documents.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const openDoc = async (id) => {
    setSelectedId(id);
    setMessage("");
    try {
      const res = await api.get(`/api/organizations/${slug}/documents/${id}/`);
      setSelected(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not open document.");
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    if (limits?.max_bytes && file.size > limits.max_bytes) {
      setError(`File must be ${limits.max_mb} MB or smaller.`);
      return;
    }
    setUploading(true);
    setError("");
    setMessage("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title.trim());
      fd.append("visibility", visibility);
      const res = await api.post(`/api/organizations/${slug}/documents/`, fd);
      setFile(null);
      setTitle("");
      setVisibility("private");
      setMessage("Document uploaded.");
      await load();
      setSelected(res.data);
      setSelectedId(res.data.id);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const updateVisibility = async (next) => {
    if (!selectedId) return;
    try {
      const res = await api.patch(`/api/organizations/${slug}/documents/${selectedId}/`, {
        visibility: next,
      });
      setSelected(res.data);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not update visibility.");
    }
  };

  const share = async (payload) => {
    if (!selectedId) return;
    try {
      const res = await api.post(
        `/api/organizations/${slug}/documents/${selectedId}/shares/`,
        payload
      );
      setSelected(res.data);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not share.");
    }
  };

  const revoke = async (shareId) => {
    if (!selectedId) return;
    try {
      const res = await api.post(
        `/api/organizations/${slug}/documents/${selectedId}/shares/${shareId}/revoke/`
      );
      setSelected(res.data);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not revoke share.");
    }
  };

  const createList = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/organizations/${slug}/documents/share-lists/`, {
        name: newListName.trim(),
      });
      setNewListName("");
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not create list.");
    }
  };

  const acceptAttr = (limits?.allowed_extensions || []).join(",");

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {orgName}
        </Link>
        <div className="dashboard-header">
          <h1>Documents</h1>
          <p>
            Upload files with their own sharing. Default is private (only you).
            Restricted means only people, organizations, or lists you add.
          </p>
        </div>

        {loading && <p className="dashboard-empty">Loading…</p>}
        {error && <p className="dashboard-error">{error}</p>}
        {message && <p className="dashboard-success">{message}</p>}

        {!loading && (
          <>
            <form className="dashboard-card dashboard-form" onSubmit={handleUpload}>
              <h2>Upload</h2>
              <p className="dashboard-meta">
                Allowed: {limits?.allowed_label || "PDF, Office, pictures"}. Max{" "}
                {limits?.max_mb || 15} MB.
              </p>
              <div className="dashboard-field">
                <label htmlFor="doc-file">File</label>
                <input
                  id="doc-file"
                  type="file"
                  accept={acceptAttr || undefined}
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </div>
              <div className="dashboard-field">
                <label htmlFor="doc-title">Title (optional)</label>
                <input
                  id="doc-title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Friendly name"
                />
              </div>
              <div className="dashboard-field">
                <label htmlFor="doc-visibility">Visibility</label>
                <select
                  id="doc-visibility"
                  value={visibility}
                  onChange={(e) => setVisibility(e.target.value)}
                >
                  <option value="private">Private — only you</option>
                  <option value="restricted">
                    Restricted — only who you share with
                  </option>
                  <option value="public">Public — anyone</option>
                </select>
              </div>
              <button
                type="submit"
                className="dashboard-btn dashboard-btn--primary"
                disabled={uploading}
              >
                {uploading ? "Uploading…" : "Upload document"}
              </button>
            </form>

            <div className="dashboard-card">
              <h2>Your library</h2>
              {documents.length === 0 ? (
                <p className="dashboard-empty">No documents yet.</p>
              ) : (
                <ul className="hub-list">
                  {documents.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        className="dashboard-btn"
                        onClick={() => openDoc(d.id)}
                      >
                        {d.title || d.original_name}
                      </button>{" "}
                      <span className="dashboard-meta">
                        {d.visibility_label} · {formatBytes(d.size_bytes)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {selected && (
              <div className="dashboard-card">
                <h2>{selected.title || selected.original_name}</h2>
                <p className="dashboard-meta">
                  {selected.visibility_label} · {formatBytes(selected.size_bytes)} ·{" "}
                  uploaded by {selected.uploaded_by?.display_name}
                </p>
                <div className="dashboard-actions">
                  <a
                    className="dashboard-btn dashboard-btn--primary"
                    href={selected.download_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download
                  </a>
                  {selected.can_manage && (
                    <>
                      <select
                        value={selected.visibility}
                        onChange={(e) => updateVisibility(e.target.value)}
                        aria-label="Document visibility"
                      >
                        <option value="private">Private</option>
                        <option value="restricted">Restricted</option>
                        <option value="public">Public</option>
                      </select>
                      <button
                        type="button"
                        className="dashboard-btn"
                        onClick={async () => {
                          if (!window.confirm("Delete this document?")) return;
                          await api.delete(
                            `/api/organizations/${slug}/documents/${selected.id}/`
                          );
                          setSelected(null);
                          setSelectedId(null);
                          await load();
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </div>

                {selected.can_manage && selected.visibility !== "public" && (
                  <>
                    <h3>Share with</h3>
                    <p className="dashboard-meta">
                      Sharing switches the document to Restricted if it was Private.
                    </p>
                    <UserSearch
                      onPick={(u) => share({ kind: "user", username: u.username })}
                    />
                    <OrgSearch
                      excludeSlug={slug}
                      onPick={(o) =>
                        share({ kind: "organization", organization_slug: o.slug })
                      }
                    />
                    <div className="dashboard-field">
                      <label htmlFor="share-list">Custom list</label>
                      <select
                        id="share-list"
                        defaultValue=""
                        onChange={(e) => {
                          const id = Number(e.target.value);
                          if (id) share({ kind: "list", share_list_id: id });
                          e.target.value = "";
                        }}
                      >
                        <option value="">Add a custom list…</option>
                        {lists.map((lst) => (
                          <option key={lst.id} value={lst.id}>
                            {lst.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    {(selected.shares || []).length > 0 && (
                      <ul className="hub-list">
                        {selected.shares.map((s) => (
                          <li key={s.id}>
                            {s.label}{" "}
                            <span className="dashboard-meta">({s.kind})</span>{" "}
                            <button
                              type="button"
                              className="dashboard-btn"
                              onClick={() => revoke(s.id)}
                            >
                              Revoke
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="dashboard-card">
              <h2>Custom share lists</h2>
              <form className="dashboard-form" onSubmit={createList}>
                <div className="dashboard-field">
                  <label htmlFor="list-name">New list name</label>
                  <input
                    id="list-name"
                    value={newListName}
                    onChange={(e) => setNewListName(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="dashboard-btn">
                  Create list
                </button>
              </form>
              {lists.length === 0 ? (
                <p className="dashboard-empty">No lists yet.</p>
              ) : (
                <ul className="hub-list">
                  {lists.map((lst) => (
                    <li key={lst.id}>
                      <strong>{lst.name}</strong>
                      <span className="dashboard-meta">
                        {" "}
                        · {(lst.members || []).map((m) => m.label).join(", ") || "empty"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="dashboard-meta">
                Tip: create a list, then share a document to that list. Add people
                or orgs to a list from a follow-up edit (coming next if needed).
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
