import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import HostResultsPanel from "../components/HostResultsPanel";
import UpgradeRequiredModal from "../components/UpgradeRequiredModal";
import "../styles/Dashboard.css";

function emptyStandardSlide(order) {
  return {
    order,
    slide_type: "standard",
    title: "",
    prompt: "",
    question_format: "text",
    choices: [],
    fields: [],
  };
}

export default function MeetingHostPage() {
  const { slug, id } = useParams();
  const meetingId = id;

  const [live, setLive] = useState(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [startSlideId, setStartSlideId] = useState("");
  const [restartSlideId, setRestartSlideId] = useState("");
  const [newSlide, setNewSlide] = useState(emptyStandardSlide(1));
  const [showAddSlide, setShowAddSlide] = useState(false);
  const [exportSessionId, setExportSessionId] = useState("all");
  const [exporting, setExporting] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [resultsSlideId, setResultsSlideId] = useState(null);
  const [capabilities, setCapabilities] = useState(null);
  const [upgradeModal, setUpgradeModal] = useState(null);

  const canStart = capabilities?.start_meetings !== false;
  const canRunAi = capabilities?.run_new_ai_analysis !== false;
  const billingPath = `/dashboard/${slug}/billing`;

  const loadLive = useCallback(async () => {
    const res = await api.get(
      `/api/organizations/${slug}/meetings/${meetingId}/live/`
    );
    setLive(res.data);
    return res.data;
  }, [slug, meetingId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadLive();
      } catch (err) {
        if (!cancelled) {
          setError(
            err.response?.data?.detail || "Could not load meeting controls."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadLive]);

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/dashboard/`)
      .then((res) => {
        if (res.data.capabilities) setCapabilities(res.data.capabilities);
      })
      .catch(() => {});
  }, [slug]);

  useEffect(() => {
    if (loading || error) return undefined;
    const interval = setInterval(() => {
      loadLive().catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [loading, error, loadLive]);

  const runAction = async (path, body = {}) => {
    setActionError("");
    setBusy(true);
    try {
      const res = await api.post(
        `/api/organizations/${slug}/meetings/${meetingId}/${path}`,
        body
      );
      if (res.data.live) {
        setLive(res.data.live);
      } else {
        await loadLive();
      }
    } catch (err) {
      if (err.response?.data?.upgrade_required) {
        setUpgradeModal({
          title: path.includes("ai")
            ? "Run New AI Analysis"
            : path.includes("start") || path.includes("restart")
              ? "Start Meeting"
              : "Upgrade required",
          body:
            err.response.data.detail ||
            "This action requires a paid CommuniB service.",
        });
      } else {
        setActionError(err.response?.data?.detail || "Action failed.");
      }
    } finally {
      setBusy(false);
    }
  };

  const downloadExport = async (type, format) => {
    setActionError("");
    setExporting(true);
    try {
      const res = await api.get(
        `/api/organizations/${slug}/meetings/${meetingId}/export/`,
        {
          params: {
            type,
            format,
            session_id: exportSessionId,
          },
          responseType: format === "csv" ? "blob" : "json",
        }
      );
      if (format === "csv") {
        const blob = new Blob([res.data], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `meeting-${meetingId}-${type}-session-${exportSessionId}.csv`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const blob = new Blob([JSON.stringify(res.data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `meeting-${meetingId}-${type}-session-${exportSessionId}.json`;
        link.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setActionError(err.response?.data?.detail || "Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const handleAddSlide = async (e) => {
    e.preventDefault();
    setActionError("");
    setBusy(true);
    try {
      const payload = {
        slides: [
          {
            order: (live?.slides?.length || 0) + 1,
            slide_type: newSlide.slide_type,
            title: newSlide.title.trim(),
            prompt: newSlide.prompt.trim(),
            question_format:
              newSlide.slide_type === "standard" ? newSlide.question_format : "",
            choices:
              newSlide.slide_type === "standard" &&
              ["single_choice", "multi_choice"].includes(newSlide.question_format)
                ? newSlide.choices
                : [],
            fields: [],
          },
        ],
      };
      const res = await api.post(
        `/api/organizations/${slug}/meetings/${meetingId}/slides/add/`,
        payload
      );
      setLive(res.data.live);
      setShowAddSlide(false);
      setNewSlide(emptyStandardSlide((live?.slides?.length || 0) + 2));
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not add slide.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p>Loading host controls...</p>
        </main>
      </div>
    );
  }

  if (error || !live) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p className="dashboard-error">{error || "Meeting not found."}</p>
          <Link to={`/dashboard/${slug}`} className="dashboard-back">
            ← Back to dashboard
          </Link>
        </main>
      </div>
    );
  }

  const sessionStatus = live.session.status;
  const isLive = sessionStatus === "live";
  const isPaused = sessionStatus === "paused";
  const isScheduled = sessionStatus === "scheduled";
  const isEnded = sessionStatus === "ended";
  const canControlSlides = isLive || isPaused;
  const canViewResults = isLive || isPaused || isEnded;
  const currentSlideId = live.session?.current_slide_id;
  const analyzableSlides = (live.slides || []).filter(
    (s) =>
      s.is_analyzable ||
      ["standard", "issue_card", "political_issue_card"].includes(s.slide_type)
  );

  const openResults = (slideId) => {
    const target =
      slideId ||
      currentSlideId ||
      analyzableSlides.find((s) => s.response_count > 0)?.id ||
      analyzableSlides[0]?.id;
    setResultsSlideId(target);
    setShowResults(true);
  };

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main dashboard-main--wide">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Host: {live.meeting_title}</h1>
          <p>
            Session #{live.session.session_number} · {sessionStatus} ·{" "}
            {live.session.attendance_count} in room
          </p>
          <Link to={`/m/${meetingId}`} target="_blank" rel="noopener noreferrer">
            Open participant view
          </Link>
        </div>

        {actionError && <p className="dashboard-error">{actionError}</p>}

        <div className="host-controls">
          {isScheduled && (
            <div className="dashboard-card">
              <h2>Start meeting</h2>
              <div className="dashboard-field">
                <label>Start from slide (optional)</label>
                <select
                  value={startSlideId}
                  onChange={(e) => setStartSlideId(e.target.value)}
                >
                  <option value="">First slide</option>
                  {live.slides.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.order} — {s.title || s.prompt || s.slide_type}
                    </option>
                  ))}
                </select>
              </div>
              {canStart ? (
                <button
                  type="button"
                  className="dashboard-btn dashboard-btn--primary"
                  disabled={busy}
                  onClick={() =>
                    runAction("start/", {
                      slide_id: startSlideId ? Number(startSlideId) : undefined,
                    })
                  }
                >
                  Start meeting
                </button>
              ) : (
                <div className="dashboard-locked-action">
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--locked"
                    aria-label="Start meeting requires Basic or higher"
                    onClick={() =>
                      setUpgradeModal({
                        title: "Start Meeting",
                        body: "Starting meetings requires CommuniB Basic or higher. You can still view previous meeting results.",
                      })
                    }
                  >
                    🔒 Start meeting
                  </button>
                  <p className="dashboard-lock-hint">Requires Basic or higher</p>
                </div>
              )}
            </div>
          )}

          {canControlSlides && (
            <div className="dashboard-card">
              <h2>Session controls</h2>
              <div className="host-control-row">
                {isLive && (
                  <button
                    type="button"
                    className="dashboard-btn"
                    disabled={busy}
                    onClick={() => runAction("pause/")}
                  >
                    Pause
                  </button>
                )}
                {isPaused && (
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--primary"
                    disabled={busy}
                    onClick={() => runAction("resume/")}
                  >
                    Resume
                  </button>
                )}
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={() => runAction("end/")}
                >
                  End meeting
                </button>
              </div>
            </div>
          )}

          {canControlSlides && (
            <div className="dashboard-card">
              <h2>Slide navigation</h2>
              <p className="dashboard-meta">
                Current responses on slide: {live.session.current_slide_response_count}
              </p>
              <div className="host-control-row">
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={() => runAction("slides/prev/")}
                >
                  ← Previous
                </button>
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={() => runAction("slides/next/")}
                >
                  Next →
                </button>
              </div>
              <div className="dashboard-field">
                <label>Jump to slide</label>
                <select
                  defaultValue=""
                  onChange={(e) => {
                    const slideId = e.target.value;
                    if (slideId) runAction("slides/go/", { slide_id: Number(slideId) });
                    e.target.value = "";
                  }}
                >
                  <option value="">Select slide…</option>
                  {live.slides.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.order} — {s.title || s.prompt || s.slide_type}
                    </option>
                  ))}
                </select>
              </div>
              {canViewResults && analyzableSlides.length > 0 && (
                <div className="host-control-row" style={{ marginTop: "0.75rem" }}>
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--primary"
                    onClick={() => openResults(currentSlideId)}
                  >
                    View live results
                  </button>
                </div>
              )}
            </div>
          )}

          {canViewResults && !canControlSlides && analyzableSlides.length > 0 && (
            <div className="dashboard-card">
              <h2>Live results</h2>
              <p className="dashboard-meta">
                Review responses from completed questions with optional demographic
                splits from the participant info slide.
              </p>
              <button
                type="button"
                className="dashboard-btn dashboard-btn--primary"
                onClick={() => openResults()}
              >
                View live results
              </button>
            </div>
          )}

          {(isEnded || canControlSlides) && (
            <div className="dashboard-card">
              <h2>Restart</h2>
              <div className="dashboard-field">
                <label>Start from slide (optional)</label>
                <select
                  value={restartSlideId}
                  onChange={(e) => setRestartSlideId(e.target.value)}
                >
                  <option value="">First slide</option>
                  {live.slides.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.order} — {s.title || s.prompt || s.slide_type}
                    </option>
                  ))}
                </select>
              </div>
              {canStart ? (
                <button
                  type="button"
                  className="dashboard-btn"
                  disabled={busy}
                  onClick={() =>
                    runAction("restart/", {
                      slide_id: restartSlideId ? Number(restartSlideId) : undefined,
                    })
                  }
                >
                  Restart meeting
                </button>
              ) : (
                <div className="dashboard-locked-action">
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--locked"
                    aria-label="Restart meeting requires Basic or higher"
                    onClick={() =>
                      setUpgradeModal({
                        title: "Restart Meeting",
                        body: "Starting meetings requires CommuniB Basic or higher. Prior session data remains available for viewing and export.",
                      })
                    }
                  >
                    🔒 Restart meeting
                  </button>
                  <p className="dashboard-lock-hint">Requires Basic or higher</p>
                </div>
              )}
              <p className="dashboard-meta">
                Creates a new session. Prior session data is kept for export.
              </p>
            </div>
          )}

          {canControlSlides && (
            <div className="dashboard-card">
              <h2>Add slide</h2>
              {!showAddSlide ? (
                <button
                  type="button"
                  className="dashboard-btn"
                  onClick={() => setShowAddSlide(true)}
                >
                  + Add question slide
                </button>
              ) : (
                <form onSubmit={handleAddSlide} className="dashboard-form">
                  <div className="dashboard-field">
                    <label>Type</label>
                    <select
                      value={newSlide.slide_type}
                      onChange={(e) =>
                        setNewSlide((s) => ({ ...s, slide_type: e.target.value }))
                      }
                    >
                      <option value="standard">Standard</option>
                      <option value="issue_card">Issue card</option>
                      <option value="political_issue_card">Political issue</option>
                    </select>
                  </div>
                  <div className="dashboard-field">
                    <label>Prompt</label>
                    <textarea
                      required
                      value={newSlide.prompt}
                      onChange={(e) =>
                        setNewSlide((s) => ({ ...s, prompt: e.target.value }))
                      }
                    />
                  </div>
                  {newSlide.slide_type === "standard" && (
                    <>
                      <div className="dashboard-field">
                        <label>Format</label>
                        <select
                          value={newSlide.question_format}
                          onChange={(e) =>
                            setNewSlide((s) => ({
                              ...s,
                              question_format: e.target.value,
                            }))
                          }
                        >
                          <option value="text">Free text</option>
                          <option value="single_choice">Single choice</option>
                          <option value="multi_choice">Multiple choice</option>
                        </select>
                      </div>
                      {["single_choice", "multi_choice"].includes(
                        newSlide.question_format
                      ) && (
                        <div className="dashboard-field">
                          <label>Choices (comma-separated)</label>
                          <input
                            value={newSlide.choices.join(", ")}
                            onChange={(e) =>
                              setNewSlide((s) => ({
                                ...s,
                                choices: e.target.value
                                  .split(",")
                                  .map((x) => x.trim())
                                  .filter(Boolean),
                              }))
                            }
                          />
                        </div>
                      )}
                    </>
                  )}
                  <div className="host-control-row">
                    <button
                      type="submit"
                      className="dashboard-btn dashboard-btn--primary"
                      disabled={busy}
                    >
                      Add slide
                    </button>
                    <button
                      type="button"
                      className="dashboard-btn"
                      onClick={() => setShowAddSlide(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>

        <div className="dashboard-card">
          <h2>Slides &amp; response counts</h2>
          <ul className="host-slide-list">
            {live.slides.map((slide) => (
              <li
                key={slide.id}
                className={`host-slide-item${slide.is_current ? " host-slide-item--current" : ""}`}
              >
                <div>
                  <strong>
                    #{slide.order} {slide.slide_type.replace(/_/g, " ")}
                  </strong>
                  {slide.title && <span> — {slide.title}</span>}
                  {slide.prompt && <p>{slide.prompt}</p>}
                </div>
                <div className="host-slide-actions">
                  <span className="host-slide-count">{slide.response_count} responses</span>
                  {canViewResults && slide.is_analyzable && slide.response_count > 0 && (
                    <button
                      type="button"
                      className="dashboard-btn dashboard-btn--small"
                      onClick={() => openResults(slide.id)}
                    >
                      Results
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="dashboard-card">
          <h2>Export results</h2>
          <p className="dashboard-meta">
            Download meeting data in the spec <code>meeting_df</code> column layout.
            {live.is_anonymous && " Anonymous meetings export participant IDs only."}
          </p>
          <div className="dashboard-field">
            <label>Session</label>
            <select
              value={exportSessionId}
              onChange={(e) => setExportSessionId(e.target.value)}
            >
              <option value="all">All sessions</option>
              {(live.sessions || []).map((s) => (
                <option key={s.id} value={s.id}>
                  Session #{s.session_number} ({s.status})
                </option>
              ))}
            </select>
          </div>
          <div className="host-control-row">
            <button
              type="button"
              className="dashboard-btn dashboard-btn--primary"
              disabled={exporting}
              onClick={() => downloadExport("responses", "csv")}
            >
              {exporting ? "Exporting…" : "Responses CSV"}
            </button>
            <button
              type="button"
              className="dashboard-btn"
              disabled={exporting}
              onClick={() => downloadExport("responses", "json")}
            >
              Responses JSON
            </button>
            <button
              type="button"
              className="dashboard-btn"
              disabled={exporting}
              onClick={() => downloadExport("profiles", "csv")}
            >
              Profiles CSV
            </button>
            <button
              type="button"
              className="dashboard-btn"
              disabled={exporting}
              onClick={() => downloadExport("profiles", "json")}
            >
              Profiles JSON
            </button>
          </div>
          <p className="dashboard-meta">
            Exports include <code>raw_response</code>, <code>normalized_response</code>,{" "}
            <code>major_issue</code>, and <code>specific_issue</code> for political issue
            cards after AI runs.
          </p>
        </div>

        {live.ai_mode && live.ai_mode !== "none" && (
          <div className="dashboard-card">
            <h2>AI analysis</h2>
            <p className="dashboard-meta">
              Mode: <strong>{live.ai_mode.replace(/_/g, " ")}</strong>
              {live.ai_pending_count > 0 && (
                <> · {live.ai_pending_count} response(s) pending analysis</>
              )}
            </p>
            <p className="dashboard-meta">
              Responses are analyzed automatically after submit. Use this to re-run on all
              responses in the selected session (rule-based demo if no API key is configured).
            </p>
            <div className="host-control-row">
              {canRunAi ? (
                <button
                  type="button"
                  className="dashboard-btn dashboard-btn--primary"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setActionError("");
                    try {
                      await api.post(
                        `/api/organizations/${slug}/meetings/${meetingId}/ai/process/`,
                        { session_id: exportSessionId }
                      );
                      await loadLive();
                    } catch (err) {
                      if (err.response?.data?.upgrade_required) {
                        setUpgradeModal({
                          title: "Run New AI Analysis",
                          body:
                            err.response.data.detail ||
                            "Running new AI analysis requires a paid CommuniB service.",
                        });
                      } else {
                        setActionError(
                          err.response?.data?.detail || "AI processing failed."
                        );
                      }
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Run AI on session
                </button>
              ) : (
                <div className="dashboard-locked-action">
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--locked"
                    aria-label="Run new AI analysis requires paid service"
                    onClick={() =>
                      setUpgradeModal({
                        title: "Run New AI Analysis",
                        body: "Running new AI analysis requires a paid CommuniB service. Previously generated AI summaries remain available.",
                      })
                    }
                  >
                    🔒 Run new AI analysis
                  </button>
                  <p className="dashboard-lock-hint">Requires paid service</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {showResults && (
        <HostResultsPanel
          slug={slug}
          meetingId={meetingId}
          slides={live.slides}
          demographicFields={live.demographic_fields}
          defaultSlideId={resultsSlideId}
          onClose={() => setShowResults(false)}
        />
      )}

      <UpgradeRequiredModal
        open={Boolean(upgradeModal)}
        title={upgradeModal?.title || ""}
        body={upgradeModal?.body || ""}
        billingPath={billingPath}
        onClose={() => setUpgradeModal(null)}
      />
    </div>
  );
}
