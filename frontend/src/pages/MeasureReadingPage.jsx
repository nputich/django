import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import api from "../api";
import { ACCESS_TOKEN } from "../constants";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/MeasureReading.css";

function comparable(text) {
  return (text || "").replace(/[ \t\r\n]+/g, "");
}

function WrappedLine({ value, className, onChange, autoFocus, onBlur }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return (
    <textarea
      ref={ref}
      rows={1}
      className={className}
      value={value}
      autoFocus={autoFocus}
      onBlur={onBlur}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function currentUserId() {
  const token = localStorage.getItem(ACCESS_TOKEN);
  if (!token) return null;
  try {
    return jwtDecode(token).user_id;
  } catch {
    return null;
  }
}

export default function MeasureReadingPage() {
  const { slug, measureId } = useParams();
  const [measures, setMeasures] = useState([]);
  const [measure, setMeasure] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ session_year: 2025, chamber: "H", bill_number: "" });
  const [lines, setLines] = useState([]);
  const [baseLines, setBaseLines] = useState([]);
  const [reviewIds, setReviewIds] = useState([]);
  const [reviewMessage, setReviewMessage] = useState("");
  const [pickedChanges, setPickedChanges] = useState([]);
  const [editingLine, setEditingLine] = useState(null);
  const me = currentUserId();

  const base = `/api/organizations/${slug}/plugins/measure-reading/measures/`;

  const loadList = () => {
    api.get(base).then((res) => setMeasures(res.data)).catch((err) => {
      setError(err.response?.data?.detail || "Could not load measures.");
    });
  };

  const loadOne = (resetLines) => {
    if (!measureId) return;
    api.get(`${base}${measureId}/`).then((res) => {
      setMeasure(res.data);
      if (resetLines) {
        const next = (res.data.body || "").split("\n");
        setBaseLines(next);
        setLines(next);
      }
    }).catch((err) => {
      setError(err.response?.data?.detail || "Could not open this measure.");
    });
  };

  useEffect(() => {
    loadList();
    loadOne(true);
  }, [slug, measureId]);

  useEffect(() => {
    if (!measureId) return undefined;
    const timer = setInterval(() => loadOne(false), 4000);
    return () => clearInterval(timer);
  }, [measureId, slug]);

  const loadSource = async (event) => {
    event.preventDefault();
    setError("");
    try {
      const res = await api.post(base, {
        session_year: Number(form.session_year),
        chamber: form.chamber,
        bill_number: Number(form.bill_number),
      });
      window.location.assign(`/dashboard/${slug}/plugins/measure-reading/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load that source.");
    }
  };

  const editLine = (index, value) => {
    setLines((current) => current.map((line, lineIndex) => (lineIndex === index ? value : line)));
  };

  const toggleChange = (change) => {
    setPickedChanges((current) => {
      const on = current.includes(change.id);
      const next = on ? current.filter((id) => id !== change.id) : [...current, change.id];
      setLines((rows) => rows.map((line, index) => (index === change.line_index ? (on ? baseLines[index] : change.edited) : line)));
      return next;
    });
  };

  const submitRevision = async () => {
    setError("");
    const res = await api.post(`${base}${measureId}/revisions/`, { body: lines.join("\n") });
    setMeasure(res.data);
    setNotice("Revision submitted.");
  };

  const requestReview = async () => {
    setError("");
    setNotice("");
    try {
      const res = await api.post(`${base}${measureId}/review-requests/`, {
        user_ids: reviewIds,
        message: reviewMessage,
      });
      setNotice(`Review request sent to ${res.data.sent.join(", ") || "no one"}.`);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not send the review request.");
    }
  };

  const colleagues = (measure?.colleagues || []).filter((person) => person.user_id !== me);
  const otherChanges = (measure?.changes || []).filter((change) => {
    const seat = (measure.members || []).find((member) => member.id === change.member_id);
    return seat && seat.user_id !== me;
  });

  return (
    <div className="dashboard-page">
      <AppHeader />
      <main className="dashboard-main measure-screen">
        <Link to={`/dashboard/${slug}`}>Back to dashboard</Link>
        <h1>Measure Reading</h1>
        {error && <p className="dashboard-error">{error}</p>}
        {notice && <p>{notice}</p>}
        {!measureId && (
          <>
            <form onSubmit={loadSource} className="measure-load">
              <label>
                Session
                <input value={form.session_year} onChange={(e) => setForm({ ...form, session_year: e.target.value })} />
              </label>
              <label>
                Chamber
                <select value={form.chamber} onChange={(e) => setForm({ ...form, chamber: e.target.value })}>
                  <option value="H">House</option>
                  <option value="S">Senate</option>
                </select>
              </label>
              <label>
                Number
                <input value={form.bill_number} onChange={(e) => setForm({ ...form, bill_number: e.target.value })} required />
              </label>
              <button type="submit">Load source</button>
            </form>
            <ul>
              {measures.map((row) => (
                <li key={row.id}>
                  <Link to={`/dashboard/${slug}/plugins/measure-reading/${row.id}`}>{row.title || row.external_key}</Link>
                </li>
              ))}
            </ul>
          </>
        )}
        {measure && (
          <div className="measure-layout">
            <aside className="measure-side">
              <h2>Ask for review</h2>
              {colleagues.map((person) => (
                <label key={person.user_id} className="measure-check">
                  <input
                    type="checkbox"
                    checked={reviewIds.includes(person.user_id)}
                    onChange={() => {
                      setReviewIds((current) => (
                        current.includes(person.user_id)
                          ? current.filter((id) => id !== person.user_id)
                          : [...current, person.user_id]
                      ));
                    }}
                  />
                  {person.username}
                </label>
              ))}
              <textarea
                rows={4}
                placeholder="Message for their inbox"
                value={reviewMessage}
                onChange={(e) => setReviewMessage(e.target.value)}
              />
              <button type="button" onClick={requestReview}>Request review</button>
            </aside>
            <section className="measure-column">
              <p className="measure-kicker">Title</p>
              <h2 className="measure-title">{measure.title}</h2>
              {measure.summary && <p className="measure-summary">{measure.summary}</p>}
              <p className="measure-enter-warning">Spaces, tabs, and new lines are ignored when comparing differences.</p>
              <article className="measure-document">
              <p className="measure-page-label">Document</p>
              {baseLines.map((original, index) => {
                const edited = lines[index] ?? "";
                const changed = comparable(edited) !== comparable(original);
                const open = editingLine === index || changed;
                return (
                  <div key={index} className="measure-line">
                    {open ? (
                      <>
                        {changed && <p className="measure-original is-replaced">{original}</p>}
                        <div className={changed ? "measure-suggestion" : undefined}>
                          <WrappedLine
                            className="measure-inline"
                            value={edited}
                            autoFocus={editingLine === index}
                            onChange={(value) => editLine(index, value)}
                            onBlur={() => {
                              if (comparable(lines[index] ?? "") === comparable(original)) setEditingLine(null);
                            }}
                          />
                        </div>
                      </>
                    ) : (
                      <p className="measure-original" onClick={() => setEditingLine(index)}>{original}</p>
                    )}
                  </div>
                );
              })}
              </article>
              <button type="button" className="measure-submit" onClick={submitRevision}>Submit revision</button>
            </section>
            <aside className="measure-side">
              <h2>Changes from others</h2>
              {otherChanges.map((change) => (
                <label key={change.id} className={`measure-check texture-${change.color_index}`}>
                  <input
                    type="checkbox"
                    checked={pickedChanges.includes(change.id)}
                    onChange={() => toggleChange(change)}
                  />
                  <span>
                    <strong>{change.label}</strong>
                    <br />
                    {change.edited}
                  </span>
                </label>
              ))}
              {otherChanges.length === 0 && <p>No one else has submitted a line change.</p>}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
