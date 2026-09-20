import { useEffect, useState } from "react";
import api from "../api";
import "../styles/Tags.css";

function joinNames(names) {
  if (!names.length) return "";
  if (names.length === 1) return names[0];
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** Mirrors backend meeting_sharing.disclosure_text so organizers see a live preview. */
export function previewDisclosure({ sharedWithNames, aggregateNotice, isAnonymous }) {
  const parts = [];
  if (sharedWithNames.length) parts.push(`Results may be shared with ${joinNames(sharedWithNames)}.`);
  if (aggregateNotice) {
    parts.push(
      "We may also share anonymous combined results with policymakers not listed here."
    );
  }
  if (isAnonymous) {
    parts.push(
      "Anonymous meeting: we do not store your name with your answers. " +
        "Organizers can still read the answers and any details you share. " +
        "Demographic comparisons are only shown when every group is large enough " +
        "so no one is singled out."
    );
  } else {
    parts.push(
      "This meeting is not anonymous. Organizers may connect your answers to " +
        "information you provide. " +
        "Demographic comparisons are only shown when every group is large enough " +
        "so no one is singled out."
    );
  }
  return parts.join(" ");
}

function OrgSearch({ excludeSlug, excludeSlugs = [], onPick }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .get("/api/organizations/lookup/", { params: { q: q.trim(), exclude: excludeSlug } })
        .then((res) => setResults(res.data.results.filter((o) => !excludeSlugs.includes(o.slug))))
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(handle);
  }, [q, excludeSlug, excludeSlugs]);

  return (
    <div className="tag-picker">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search organizations to share results with…"
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

/**
 * Two modes:
 *  - draft (Create): `pending` list of {name, slug} held by the parent; no API calls.
 *  - live  (Edit):   `meetingId` set; grants/revokes hit the API immediately.
 */
export default function MeetingSharingFields({
  orgSlug,
  meetingId = null,
  isAnonymous,
  aggregateNotice,
  onAggregateNoticeChange,
  pending = [],
  onPendingChange,
}) {
  const [shares, setShares] = useState([]);
  const [hasStarted, setHasStarted] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => {
    if (!meetingId) return;
    api
      .get(`/api/organizations/${orgSlug}/meetings/${meetingId}/shares/`)
      .then((res) => {
        setShares(res.data.shares);
        setHasStarted(res.data.has_started);
      })
      .catch(() => {});
  };

  useEffect(load, [orgSlug, meetingId]); // eslint-disable-line react-hooks/exhaustive-deps

  const grant = async (org) => {
    setError("");
    if (!meetingId) {
      if (!pending.some((p) => p.slug === org.slug)) onPendingChange([...pending, org]);
      return;
    }
    setBusy(true);
    try {
      const res = await api.post(`/api/organizations/${orgSlug}/meetings/${meetingId}/shares/`, {
        organization_slug: org.slug,
      });
      setShares(res.data.shares);
      setHasStarted(res.data.has_started);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not share.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (share) => {
    if (
      !window.confirm(
        `Stop sharing with ${share.organization.name}? They will keep buckets and totals, but lose full-data access.`
      )
    )
      return;
    setBusy(true);
    try {
      const res = await api.post(
        `/api/organizations/${orgSlug}/meetings/${meetingId}/shares/${share.id}/revoke/`
      );
      setShares(res.data.shares);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not revoke.");
    } finally {
      setBusy(false);
    }
  };

  const activeNames = meetingId
    ? shares.filter((s) => s.status === "active" && s.declared_before_start).map((s) => s.organization.name)
    : pending.map((p) => p.name);
  const excluded = meetingId ? shares.map((s) => s.organization.slug) : pending.map((p) => p.slug);

  return (
    <div className="dashboard-field">
      <fieldset className="dashboard-fieldset">
        <legend>Share results with other organizations</legend>
        <p className="dashboard-meta">
          Organizations you list here <strong>before the meeting starts</strong> receive the full
          anonymous dataset. Anyone added afterwards, or removed later, only receives buckets and
          totals. Participants see who is listed on the first slide.
        </p>
        {hasStarted && (
          <p className="dashboard-meta">
            This meeting has already started — new organizations will receive buckets and totals only.
          </p>
        )}

        <OrgSearch excludeSlug={orgSlug} excludeSlugs={excluded} onPick={grant} />

        <ul className="share-list dashboard-list">
          {meetingId
            ? shares.map((s) => (
                <li key={s.id}>
                  <span>
                    {s.organization.name}{" "}
                    <span className={`share-access share-access--${s.effective_access}`}>
                      {s.effective_access_label}
                    </span>
                    {s.status === "revoked" && <span className="dashboard-meta"> · revoked</span>}
                  </span>
                  {s.status === "active" && (
                    <button
                      type="button"
                      className="dashboard-link-btn"
                      disabled={busy}
                      onClick={() => revoke(s)}
                    >
                      Stop sharing
                    </button>
                  )}
                </li>
              ))
            : pending.map((p) => (
                <li key={p.slug}>
                  <span>
                    {p.name} <span className="share-access">Full data</span>
                  </span>
                  <button
                    type="button"
                    className="dashboard-link-btn"
                    onClick={() => onPendingChange(pending.filter((x) => x.slug !== p.slug))}
                  >
                    Remove
                  </button>
                </li>
              ))}
        </ul>
        {error && <p className="dashboard-error">{error}</p>}

        <label className="dashboard-radio-row">
          <input
            type="checkbox"
            checked={aggregateNotice}
            onChange={(e) => onAggregateNoticeChange(e.target.checked)}
          />{" "}
          Tell participants that anonymous combined results may also be shared with policymakers
          and decision makers not listed here
        </label>

        <div className="meeting-disclosure">
          <p className="dashboard-meta" style={{ marginBottom: "0.25rem" }}>
            Participants will read:
          </p>
          <p>
            {previewDisclosure({
              sharedWithNames: activeNames,
              aggregateNotice,
              isAnonymous,
            })}
          </p>
        </div>
      </fieldset>
    </div>
  );
}
