import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import { liveResultsPath } from "../meetingFlyer";
import ResultsBarChart from "./ResultsBarChart";
import "../styles/LiveResults.css";

const AI_LABELS = {
  disabled: "AI analysis: off",
  no_responses: "AI analysis: waiting for answers",
  pending: "AI analysis: not run yet",
  partial: "AI analysis: partly updated",
  ready: "AI analysis: up to date",
};

function AiStatus({ ai }) {
  if (!ai || ai.status === "not_applicable" || !AI_LABELS[ai.status]) return null;
  return (
    <div className="live-results-ai">
      <span className={`live-results-ai-badge live-results-ai-badge--${ai.status}`}>
        {AI_LABELS[ai.status]}
      </span>
      {ai.message && <p className="live-results-ai-message">{ai.message}</p>}
    </div>
  );
}

function formatTime(date) {
  if (!date) return "";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

/**
 * Participant view of organizer-released results. Loads on mount and when the
 * participant taps Refresh; never polls in the background.
 *
 * kind: "meeting" (identity = attendance_id) or "survey" (identity = response_session).
 */
export default function LiveResultsPanel({ kind, resourceId, identity, showOpenLink = false }) {
  const [selectedId, setSelectedId] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState(null);

  const isSurvey = kind === "survey";

  const load = useCallback(
    async (itemId) => {
      if (!identity || !resourceId) return;
      setLoading(true);
      const params = isSurvey ? { response_session: identity } : { attendance_id: identity };
      if (itemId) params[isSurvey ? "question_id" : "slide_id"] = itemId;
      try {
        const res = await api.get(
          `/api/${isSurvey ? "surveys" : "meetings"}/${resourceId}/live-results/`,
          { params }
        );
        setData(res.data);
        setSelectedId(res.data.result?.item_id ?? null);
        setError("");
        setLoadedAt(new Date());
      } catch (err) {
        if (itemId && err.response?.data?.code === "not_released") {
          await load(null);
          return;
        }
        setError(err.response?.data?.detail || "Could not load results. Try Refresh.");
      } finally {
        setLoading(false);
      }
    },
    [identity, resourceId, isSurvey]
  );

  useEffect(() => {
    load(null);
  }, [load]);

  const items = data?.released_items || [];
  const result = data?.result;

  return (
    <section className="live-results-panel" aria-live="polite">
      <div className="live-results-header">
        <h2>Live results</h2>
        <button
          type="button"
          className="live-results-refresh"
          disabled={loading}
          onClick={() => load(selectedId)}
        >
          {loading ? "Refreshing…" : "Refresh results"}
        </button>
      </div>
      {loadedAt && <p className="live-results-updated">Updated {formatTime(loadedAt)}</p>}

      {error && <p className="landing-code-error">{error}</p>}

      {data && items.length === 0 && !error && (
        <p className="resource-note">
          No results have been shared yet. The {isSurvey ? "organizer" : "facilitator"} shares
          results one question at a time. Tap <strong>Refresh results</strong> to check again.
        </p>
      )}

      {items.length > 1 && (
        <label className="resource-field live-results-picker">
          <span>Question</span>
          <select
            value={selectedId ?? ""}
            disabled={loading}
            onChange={(e) => load(Number(e.target.value))}
          >
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
      )}

      {result && (
        <div className="live-results-body">
          <h3>{result.title}</h3>
          {result.prompt && <p className="live-results-prompt">{result.prompt}</p>}
          <AiStatus ai={result.ai} />
          <p className="live-results-count">
            {result.total_respondents} {result.total_respondents === 1 ? "person" : "people"}{" "}
            responded
          </p>
          <ResultsBarChart bars={result.bars} />
        </div>
      )}

      {showOpenLink && (
        <Link to={liveResultsPath(kind, resourceId)} className="live-results-open-link">
          Open results on its own page
        </Link>
      )}
    </section>
  );
}
