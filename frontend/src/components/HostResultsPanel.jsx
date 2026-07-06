import { useCallback, useEffect, useState } from "react";
import api from "../api";
import "../styles/HostResults.css";

const isLocalDev = import.meta.env.DEV;

function isAnalyzableSlide(slide) {
  return (
    slide?.is_analyzable ||
    ["standard", "issue_card", "political_issue_card"].includes(slide?.slide_type)
  );
}

function BarChart({ bars, compact = false }) {
  if (!bars?.length) {
    return <p className="dashboard-meta host-results-empty">No responses yet.</p>;
  }

  return (
    <div
      className={`host-bar-chart${compact ? " host-bar-chart--compact" : ""}`}
      aria-label="Results chart"
    >
      {bars.map((bar) => (
        <div key={bar.label} className="host-bar-row">
          <span className="host-bar-label" title={bar.label}>
            {bar.label}
          </span>
          <div className="host-bar-track">
            <div
              className="host-bar-fill"
              style={{ width: `${bar.percent}%` }}
            />
          </div>
          <span className="host-bar-count">{bar.count}</span>
        </div>
      ))}
    </div>
  );
}

function CompareColumn({ title, subtitle, bars }) {
  return (
    <div className="host-results-column">
      <div className="host-results-column-header">
        <h3>{title}</h3>
        {subtitle && <p className="host-results-column-meta">{subtitle}</p>}
      </div>
      <BarChart bars={bars} compact />
    </div>
  );
}

function IndividualResponses({ responses, splitField, splitFieldLabel }) {
  if (!responses?.length) {
    return (
      <p className="dashboard-meta host-results-individual-empty">
        No individual responses yet.
      </p>
    );
  }

  return (
    <ul className="host-results-individual-list">
      {responses.map((row) => (
        <li key={row.response_id}>
          <strong>{row.participant_label}</strong>
          {splitField && row.demographics?.[splitField] && (
            <span className="host-results-individual-demo">
              {" "}
              · {splitFieldLabel || splitField}: {row.demographics[splitField]}
            </span>
          )}
          <span className="host-results-individual-answer"> — {row.answer}</span>
        </li>
      ))}
    </ul>
  );
}

export default function HostResultsPanel({
  slug,
  meetingId,
  slides,
  demographicFields,
  defaultSlideId,
  onClose,
}) {
  const analyzableSlides = (slides || []).filter(isAnalyzableSlide);
  const initialSlideId =
    defaultSlideId &&
    analyzableSlides.some((s) => s.id === defaultSlideId)
      ? defaultSlideId
      : analyzableSlides[0]?.id || "";

  const [slideId, setSlideId] = useState(initialSlideId);
  const [splitField, setSplitField] = useState("");
  const [showIndividuals, setShowIndividuals] = useState(false);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadAnalytics = useCallback(async () => {
    if (!slideId) return;
    try {
      const params = { slide_id: slideId, limit: 10 };
      if (splitField) {
        params.split_field = splitField;
        params.split_compare = "1";
      }
      if (isLocalDev && showIndividuals) {
        params.include_individual = "1";
      }
      const res = await api.get(
        `/api/organizations/${slug}/meetings/${meetingId}/analytics/`,
        { params }
      );
      setAnalytics(res.data);
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load results.");
    } finally {
      setLoading(false);
    }
  }, [slug, meetingId, slideId, splitField, showIndividuals]);

  useEffect(() => {
    setLoading(true);
    loadAnalytics();
  }, [loadAnalytics]);

  useEffect(() => {
    if (!slideId) return undefined;
    const interval = setInterval(() => {
      loadAnalytics();
    }, 3000);
    return () => clearInterval(interval);
  }, [slideId, loadAnalytics]);

  const fields = analytics?.demographic_fields?.length
    ? analytics.demographic_fields
    : demographicFields || [];

  const selectedField = fields.find((f) => f.key === splitField);
  const isCompare = Boolean(splitField && analytics?.comparisons);
  const splitFieldLabel =
    analytics?.split?.field_label || selectedField?.label || splitField;

  return (
    <div
      className="host-results-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="host-results-title"
    >
      <div
        className={`host-results-panel${isCompare ? " host-results-panel--wide" : ""}`}
      >
        <div className="host-results-header">
          <h2 id="host-results-title">Live results</h2>
          <button
            type="button"
            className="host-results-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="host-results-controls">
          <div className="dashboard-field">
            <label htmlFor="host-results-slide">Question slide</label>
            <select
              id="host-results-slide"
              value={slideId}
              onChange={(e) => setSlideId(Number(e.target.value))}
            >
              {analyzableSlides.map((slide) => (
                <option key={slide.id} value={slide.id}>
                  #{slide.order} — {slide.title || slide.prompt || slide.slide_type} (
                  {slide.response_count} responses)
                </option>
              ))}
            </select>
          </div>

          <div className="dashboard-field">
            <label htmlFor="host-results-split">Compare by (optional)</label>
            <select
              id="host-results-split"
              value={splitField}
              onChange={(e) => setSplitField(e.target.value)}
            >
              <option value="">All participants</option>
              {fields.map((field) => (
                <option key={field.key} value={field.key}>
                  {field.label}
                </option>
              ))}
            </select>
          </div>

          {isLocalDev && (
            <label className="host-results-debug-toggle">
              <input
                type="checkbox"
                checked={showIndividuals}
                onChange={(e) => setShowIndividuals(e.target.checked)}
              />
              Show individual answers (local only)
            </label>
          )}
        </div>

        {analytics && (
          <p className="host-results-meta">
            {isCompare ? (
              <>
                Comparing <strong>{analytics.total_respondents}</strong> participant
                {analytics.total_respondents === 1 ? "" : "s"} by{" "}
                <strong>{splitFieldLabel}</strong>
                {analytics.comparisons.length > 0 && (
                  <>
                    {" "}
                    across <strong>{analytics.comparisons.length}</strong> group
                    {analytics.comparisons.length === 1 ? "" : "s"}
                  </>
                )}
              </>
            ) : (
              <>
                <strong>{analytics.total_respondents}</strong> participant
                {analytics.total_respondents === 1 ? "" : "s"} responded
                {analytics.response_row_count !== analytics.total_respondents && (
                  <> · {analytics.response_row_count} total entries</>
                )}
              </>
            )}
            {loading && " · Updating…"}
          </p>
        )}

        {error && <p className="dashboard-error">{error}</p>}

        <div className="host-results-body">
          {!error && analytics && isCompare && (
            <>
              {analytics.comparisons.length === 0 ? (
                <p className="dashboard-meta">
                  No {splitFieldLabel.toLowerCase()} values submitted yet. Responses
                  will appear here once participants fill in the participant info
                  slide.
                </p>
              ) : (
                <div className="host-results-compare-scroll">
                  <div className="host-results-compare">
                    <CompareColumn
                      title="All"
                      subtitle={`${analytics.overall?.filtered_respondents ?? analytics.total_respondents} participants`}
                      bars={analytics.overall?.bars || []}
                    />
                    {analytics.comparisons.map((group) => (
                      <CompareColumn
                        key={group.value}
                        title={group.value}
                        subtitle={`${group.filtered_respondents} participant${
                          group.filtered_respondents === 1 ? "" : "s"
                        }`}
                        bars={group.bars}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {!error && analytics && !isCompare && analytics.bars?.length === 0 && (
            <p className="dashboard-meta">No responses yet for this slide.</p>
          )}

          {!error && analytics && !isCompare && analytics.bars?.length > 0 && (
            <BarChart bars={analytics.bars} />
          )}

          {isLocalDev && showIndividuals && analytics && (
            <div className="host-results-individual">
              <h3>Individual answers</h3>
              <IndividualResponses
                responses={analytics.individual_responses}
                splitField={splitField}
                splitFieldLabel={splitFieldLabel}
              />
            </div>
          )}
        </div>

        <p className="dashboard-meta host-results-footnote">
          Results refresh every few seconds while this panel is open.
          {isCompare && " Scroll sideways to compare groups; scroll down if needed."}
        </p>
      </div>
    </div>
  );
}
