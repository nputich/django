import { useEffect, useState } from "react";
import api from "../api";
import { TagChips } from "./TagPicker";
import "../styles/Tags.css";

function newClientId(prefix = "slide") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function slideFromReusable(item) {
  return {
    clientId: newClientId(),
    slide_type: item.slide_type,
    title: item.title || "",
    prompt: item.prompt || "",
    question_format: item.question_format || (item.slide_type === "standard" ? "text" : ""),
    choices: Array.isArray(item.choices) ? item.choices.join(", ") : "",
    fields: [],
    tag_ids: item.tag_ids || [],
    tags: item.tags || [],
  };
}

/**
 * "Reuse questions from a past meeting": pick any earlier meeting, planned
 * agenda questions come pre-checked, live-added ones are offered as chips.
 */
export default function ReuseQuestionsPanel({ orgSlug, excludeMeetingId = null, onAdd }) {
  const [open, setOpen] = useState(false);
  const [meetings, setMeetings] = useState([]);
  const [selectedMeeting, setSelectedMeeting] = useState("");
  const [data, setData] = useState(null);
  const [checked, setChecked] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || meetings.length) return;
    api
      .get(`/api/organizations/${orgSlug}/dashboard/`)
      .then((res) => {
        const list = (res.data.meetings || []).filter((m) => m.id !== excludeMeetingId);
        setMeetings(list);
      })
      .catch(() => setError("Could not load past meetings."));
  }, [open, orgSlug, excludeMeetingId, meetings.length]);

  useEffect(() => {
    if (!selectedMeeting) {
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    api
      .get(`/api/organizations/${orgSlug}/meetings/${selectedMeeting}/reusable-slides/`)
      .then((res) => {
        setData(res.data);
        setChecked(new Set(res.data.planned.map((s) => s.id)));
      })
      .catch(() => setError("Could not load that meeting's questions."))
      .finally(() => setLoading(false));
  }, [orgSlug, selectedMeeting]);

  const toggle = (id) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const addSelected = () => {
    if (!data) return;
    const all = [...data.planned, ...data.live_added];
    const picked = all.filter((s) => checked.has(s.id)).map(slideFromReusable);
    if (!picked.length) return;
    onAdd(picked);
    setSelectedMeeting("");
    setData(null);
    setOpen(false);
  };

  if (!open) {
    return (
      <button type="button" className="dashboard-btn" onClick={() => setOpen(true)}>
        Reuse questions from a past meeting
      </button>
    );
  }

  return (
    <div className="reuse-panel">
      <div className="dashboard-section-header">
        <h3>Reuse questions</h3>
        <button type="button" className="dashboard-link-btn" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      <p className="dashboard-meta">
        Pick any past meeting. Its planned agenda questions are pre-selected; questions that were
        added live during that meeting are offered below so you can promote them to this agenda.
        Reused questions keep their tags, so answers group together in reports.
      </p>
      <div className="dashboard-field">
        <label>Past meeting</label>
        <select value={selectedMeeting} onChange={(e) => setSelectedMeeting(e.target.value)}>
          <option value="">Choose a meeting…</option>
          {meetings.map((m) => (
            <option key={m.id} value={m.id}>
              {m.title} · {m.status}
            </option>
          ))}
        </select>
      </div>
      {loading && <p className="dashboard-meta">Loading…</p>}
      {error && <p className="dashboard-error">{error}</p>}
      {data && (
        <>
          <h4>Planned agenda ({data.planned.length})</h4>
          {data.planned.length === 0 && <p className="dashboard-empty">No planned questions.</p>}
          <ul className="reuse-list">
            {data.planned.map((s) => (
              <li key={s.id}>
                <input
                  type="checkbox"
                  id={`reuse-${s.id}`}
                  checked={checked.has(s.id)}
                  onChange={() => toggle(s.id)}
                />
                <label htmlFor={`reuse-${s.id}`}>
                  {s.prompt || s.title}{" "}
                  <span className="dashboard-meta">
                    · {s.response_count} answers
                  </span>
                  {s.tags?.length > 0 && (
                    <>
                      {" "}
                      <TagChips tags={s.tags} small />
                    </>
                  )}
                </label>
              </li>
            ))}
          </ul>
          {data.live_added.length > 0 && (
            <>
              <h4>Added live during that meeting ({data.live_added.length})</h4>
              <p className="dashboard-meta">
                Tap to include any of these in this meeting's agenda.
              </p>
              <div>
                {data.live_added.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`reuse-chip${checked.has(s.id) ? " is-selected" : ""}`}
                    onClick={() => toggle(s.id)}
                  >
                    {s.prompt || s.title} · {s.response_count}
                  </button>
                ))}
              </div>
            </>
          )}
          <div className="dashboard-actions" style={{ marginTop: "0.75rem" }}>
            <button
              type="button"
              className="dashboard-btn dashboard-btn--primary"
              disabled={checked.size === 0}
              onClick={addSelected}
            >
              Add {checked.size} question{checked.size === 1 ? "" : "s"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
