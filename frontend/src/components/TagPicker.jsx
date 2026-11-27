import { useEffect, useMemo, useRef, useState } from "react";
import api from "../api";
import "../styles/Tags.css";

// One catalog fetch per org per page load.
const catalogCache = new Map();
const resolvedCatalogs = new Map();

export function loadTagCatalog(orgSlug, { force = false } = {}) {
  if (!orgSlug) return Promise.resolve({ tags: [], categories: [] });
  if (!force && catalogCache.has(orgSlug)) return catalogCache.get(orgSlug);
  const promise = api
    .get(`/api/organizations/${orgSlug}/question-tags/`)
    .then((res) => {
      resolvedCatalogs.set(orgSlug, res.data);
      return res.data;
    })
    .catch(() => {
      catalogCache.delete(orgSlug);
      return { tags: [], categories: [] };
    });
  catalogCache.set(orgSlug, promise);
  return promise;
}

/** Synchronous lookup of tag objects for ids, using whatever catalog has loaded. */
export function resolveTags(orgSlug, ids) {
  const catalog = resolvedCatalogs.get(orgSlug);
  if (!catalog) return [];
  const byId = new Map(catalog.tags.map((t) => [t.id, t]));
  return (ids || []).map((id) => byId.get(id)).filter(Boolean);
}

export function TagChips({ tags, onRemove, small = false }) {
  if (!tags?.length) return null;
  return (
    <span className={small ? "tag-chips tag-chips--small" : "tag-chips"}>
      {tags.map((t) => (
        <span key={t.id} className={`tag-chip tag-chip--${t.category || "custom"}`}>
          {t.label}
          {onRemove && (
            <button
              type="button"
              aria-label={`Remove tag ${t.label}`}
              onClick={() => onRemove(t.id)}
            >
              ×
            </button>
          )}
        </span>
      ))}
    </span>
  );
}

/**
 * Multi-select tag picker backed by the org's catalog (shared + custom).
 *
 * props:
 *  orgSlug        — organization slug (required for loading)
 *  value          — array of tag ids
 *  onChange(ids)  — replacement handler
 *  questionText   — optional; shows how many past uses share this text
 *  compact        — smaller layout for inline use
 */
export default function TagPicker({ orgSlug, value = [], onChange, questionText = "", compact = false }) {
  const [catalog, setCatalog] = useState({ tags: [], categories: [] });
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uses, setUses] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    let alive = true;
    loadTagCatalog(orgSlug).then((data) => alive && setCatalog(data));
    return () => {
      alive = false;
    };
  }, [orgSlug]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    const text = (questionText || "").trim();
    if (!orgSlug || text.length < 4) {
      setUses(null);
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .get(`/api/organizations/${orgSlug}/question-uses/`, { params: { text } })
        .then((res) => setUses(res.data))
        .catch(() => setUses(null));
    }, 400);
    return () => clearTimeout(handle);
  }, [orgSlug, questionText]);

  const byId = useMemo(() => new Map(catalog.tags.map((t) => [t.id, t])), [catalog]);
  const selected = value.map((id) => byId.get(id)).filter(Boolean);
  const q = query.trim().toLowerCase();
  const matches = catalog.tags.filter(
    (t) => !value.includes(t.id) && (!q || t.label.toLowerCase().includes(q) || t.slug.includes(q))
  );
  const grouped = catalog.categories
    .map((c) => ({ ...c, tags: c.tags.filter((t) => matches.some((m) => m.id === t.id)) }))
    .filter((c) => c.tags.length);
  const exactExists = catalog.tags.some((t) => t.label.toLowerCase() === q);

  const add = (id) => {
    onChange([...value, id]);
    setQuery("");
  };
  const remove = (id) => onChange(value.filter((v) => v !== id));

  const createTag = async () => {
    const label = query.trim();
    if (label.length < 2 || creating) return;
    setCreating(true);
    try {
      const res = await api.post(`/api/organizations/${orgSlug}/question-tags/`, { label });
      const data = await loadTagCatalog(orgSlug, { force: true });
      setCatalog(data);
      add(res.data.id);
    } catch {
      /* leave the query so the user can retry */
    } finally {
      setCreating(false);
    }
  };

  const totalUses = uses ? uses.other_uses.meetings + uses.other_uses.surveys : 0;
  const inheritedTags = (uses?.tags || []).filter((t) => !value.includes(t.id));

  return (
    <div className={compact ? "tag-picker tag-picker--compact" : "tag-picker"} ref={ref}>
      <div className="tag-picker-selected">
        <TagChips tags={selected} onRemove={remove} />
        <input
          type="text"
          value={query}
          placeholder={selected.length ? "Add another tag…" : "Add tags (concern, priority, housing…)"}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (matches.length && (q === "" || matches[0].label.toLowerCase().startsWith(q))) {
                add(matches[0].id);
              } else if (q.length >= 2 && !exactExists) {
                createTag();
              }
            }
            if (e.key === "Escape") setOpen(false);
          }}
        />
      </div>
      {open && (
        <div className="tag-picker-menu" role="listbox">
          {grouped.length === 0 && !q && <p className="dashboard-meta">Loading tags…</p>}
          {grouped.map((c) => (
            <div key={c.key} className="tag-picker-group">
              <p className="tag-picker-group-label">{c.label}</p>
              <div className="tag-picker-options">
                {c.tags.slice(0, 40).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={`tag-chip tag-chip--${t.category} tag-chip--option`}
                    title={t.description || ""}
                    onClick={() => add(t.id)}
                  >
                    {t.label}
                    {t.usage ? <span className="tag-chip-count">{t.usage}</span> : null}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {q.length >= 2 && !exactExists && (
            <button
              type="button"
              className="tag-picker-create"
              disabled={creating}
              onClick={createTag}
            >
              + Create tag “{query.trim()}”
            </button>
          )}
          {q.length >= 2 && grouped.length === 0 && exactExists && (
            <p className="dashboard-meta">Already added.</p>
          )}
        </div>
      )}
      {uses && totalUses > 0 && (
        <p className="tag-picker-uses dashboard-meta">
          This exact question was asked in {uses.other_uses.meetings} other meeting
          {uses.other_uses.meetings === 1 ? "" : "s"}
          {uses.other_uses.surveys
            ? ` and ${uses.other_uses.surveys} survey${uses.other_uses.surveys === 1 ? "" : "s"}`
            : ""}{" "}
          ({uses.other_uses.responses} responses). Tags you add here apply to all of them, so past
          answers show up in reports.
          {inheritedTags.length > 0 && (
            <>
              {" "}
              Already tagged: <TagChips tags={inheritedTags} small />
            </>
          )}
        </p>
      )}
    </div>
  );
}
