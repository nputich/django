import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import { TagChips, loadTagCatalog } from "../components/TagPicker";
import "../styles/Dashboard.css";
import "../styles/Tags.css";

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function monthLabel(ym) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString(undefined, { month: "short", year: "2-digit" });
}

function Bars({ counts }) {
  const entries = Object.entries(counts || {});
  const max = Math.max(1, ...entries.map(([, n]) => n));
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  return (
    <div className="report-bars">
      {entries.map(([label, n]) => (
        <ContentsRow key={label} label={label} n={n} max={max} total={total} />
      ))}
    </div>
  );
}

function ContentsRow({ label, n, max, total }) {
  return (
    <>
      <span>{label}</span>
      <div className="report-bar" aria-hidden>
        <span style={{ width: `${(n / max) * 100}%` }} />
      </div>
      <span className="dashboard-meta">
        {n} · {Math.round((n / total) * 100)}%
      </span>
    </>
  );
}

function Months({ series }) {
  const max = Math.max(1, ...series.map((s) => s.responses));
  return (
    <div className="report-months" aria-label="Responses by month">
      {series.map((s) => (
        <div key={s.month} className="report-month" title={`${monthLabel(s.month)}: ${s.responses}`}>
          <div style={{ height: `${(s.responses / max) * 100}%` }} />
          <span>{monthLabel(s.month)}</span>
        </div>
      ))}
    </div>
  );
}

function QuestionCard({ q }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="dashboard-card report-question">
      <div
        className="report-question-header"
        role="button"
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => e.key === "Enter" && setOpen((v) => !v)}
      >
        <div>
          <h3>{q.text}</h3>
          <p className="dashboard-meta">
            {q.responses} responses · {q.participants} participants · asked in{" "}
            {q.times_asked.meetings} meeting{q.times_asked.meetings === 1 ? "" : "s"}
            {q.times_asked.surveys
              ? ` and ${q.times_asked.surveys} survey${q.times_asked.surveys === 1 ? "" : "s"}`
              : ""}
          </p>
          <TagChips tags={q.tags} small />
        </div>
        <span className="dashboard-meta">{open ? "Hide" : "Details"}</span>
      </div>
      {open && (
        <>
          {q.choice_counts && <Bars counts={q.choice_counts} />}
          {q.issue_counts && (
            <>
              <p className="dashboard-meta">Political issues (AI classification)</p>
              <Bars counts={q.issue_counts} />
            </>
          )}
          {q.months.length > 1 && <Months series={q.months} />}
          {q.samples.length > 0 && (
            <>
              <p className="dashboard-meta">Recent written answers</p>
              <ul className="report-samples">
                {q.samples.map((s, i) => (
                  <li key={i}>
                    {s.text} <span className="dashboard-meta">· {s.source}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function OrgReportsPage() {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const [report, setReport] = useState(null);
  const [catalog, setCatalog] = useState({ tags: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const from = params.get("from") || isoDaysAgo(182);
  const to = params.get("to") || new Date().toISOString().slice(0, 10);
  const source = params.get("source") || "all";
  const q = params.get("q") || "";
  const tagIds = useMemo(
    () => (params.get("tags") || "").split(",").filter(Boolean).map(Number),
    [params]
  );

  const setParam = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  useEffect(() => {
    loadTagCatalog(slug).then(setCatalog);
  }, [slug]);

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .get(`/api/organizations/${slug}/reports/`, {
        params: { from, to, source, q, tags: tagIds.join(",") },
      })
      .then((res) => setReport(res.data))
      .catch((err) => setError(err.response?.data?.detail || "Could not load report."))
      .finally(() => setLoading(false));
  }, [slug, from, to, source, q, tagIds]);

  const toggleTag = (id) => {
    const next = tagIds.includes(id) ? tagIds.filter((t) => t !== id) : [...tagIds, id];
    setParam("tags", next.join(","));
  };

  const csvHref = `/api/organizations/${slug}/reports/?export=csv&from=${from}&to=${to}&source=${source}&q=${encodeURIComponent(
    q
  )}&tags=${tagIds.join(",")}`;

  const downloadCsv = async () => {
    try {
      const res = await api.get(csvHref, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${slug}-report-${from}-to-${to}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download CSV.");
    }
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to {slug}
        </Link>
        <div className="dashboard-header">
          <h1>Reports</h1>
          <p>
            See what people told you across meetings and surveys. Group by question or by tag,
            over any date range.
          </p>
        </div>

        <div className="dashboard-card">
          <div className="report-filters">
            <div className="dashboard-field">
              <label htmlFor="rep-from">From</label>
              <input id="rep-from" type="date" value={from} onChange={(e) => setParam("from", e.target.value)} />
            </div>
            <div className="dashboard-field">
              <label htmlFor="rep-to">To</label>
              <input id="rep-to" type="date" value={to} onChange={(e) => setParam("to", e.target.value)} />
            </div>
            <div className="dashboard-field">
              <label htmlFor="rep-source">Source</label>
              <select id="rep-source" value={source} onChange={(e) => setParam("source", e.target.value)}>
                <option value="all">Meetings + surveys</option>
                <option value="meetings">Meetings only</option>
                <option value="surveys">Surveys only</option>
              </select>
            </div>
            <div className="dashboard-field" style={{ flex: 1 }}>
              <label htmlFor="rep-q">Question text</label>
              <input
                id="rep-q"
                type="search"
                value={q}
                placeholder="e.g. concern, parking"
                onChange={(e) => setParam("q", e.target.value)}
              />
            </div>
            <button type="button" className="dashboard-btn" onClick={downloadCsv} disabled={!report}>
              Download CSV
            </button>
          </div>
          {tagIds.length > 0 && (
            <p className="dashboard-meta" style={{ marginTop: "0.5rem" }}>
              Filtering by tag:{" "}
              <TagChips
                tags={catalog.tags.filter((t) => tagIds.includes(t.id))}
                onRemove={toggleTag}
                small
              />
            </p>
          )}
        </div>

        {error && <p className="dashboard-error">{error}</p>}
        {loading && <p className="dashboard-meta">Loading…</p>}

        {report && (
          <>
            <div className="report-totals">
              <div className="report-total">
                <strong>{report.totals.responses}</strong> responses
              </div>
              <div className="report-total">
                <strong>{report.totals.questions}</strong> distinct questions
              </div>
              <div className="report-total">
                <strong>{report.totals.meetings}</strong> meetings
              </div>
              <div className="report-total">
                <strong>{report.totals.surveys}</strong> surveys
              </div>
            </div>

            <div className="dashboard-section" style={{ display: "grid", gap: "1rem", gridTemplateColumns: "minmax(220px, 1fr) 3fr" }}>
              <aside className="dashboard-card">
                <h2>By tag</h2>
                {report.tags.length === 0 && (
                  <p className="dashboard-empty">
                    No tagged questions in this range. Add tags to questions when you create or
                    edit a meeting or survey — they apply to past answers too.
                  </p>
                )}
                {report.tags.map((row) => (
                  <div
                    key={row.tag.id}
                    className={`report-tag-row${tagIds.includes(row.tag.id) ? " is-active" : ""}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleTag(row.tag.id)}
                    onKeyDown={(e) => e.key === "Enter" && toggleTag(row.tag.id)}
                  >
                    <span>
                      <TagChips tags={[row.tag]} small />
                    </span>
                    <span className="dashboard-meta">
                      {row.responses} · {row.questions} q
                    </span>
                  </div>
                ))}
              </aside>

              <section>
                <h2>By question</h2>
                {report.questions.length === 0 ? (
                  <p className="dashboard-empty">No responses match these filters.</p>
                ) : (
                  report.questions.map((qq) => <QuestionCard key={qq.question_key} q={qq} />)
                )}
              </section>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
