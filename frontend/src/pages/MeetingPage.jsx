import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { ensureValidSession } from "../auth";
import IssueCardForm from "../components/IssueCardForm";
import ContentBlock from "../components/ContentBlock";
import LiveResultsPanel from "../components/LiveResultsPanel";
import {
  clearMeetingParticipant,
  getMeetingParticipant,
  saveMeetingParticipant,
} from "../meetingParticipant";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/Tags.css";

const POLL_MS = 4000;

function SlidePrompt({ slide }) {
  const label = slide.title || slide.prompt;
  return (
    <>
      <h2>{label}</h2>
      {slide.title && slide.prompt && <p>{slide.prompt}</p>}
    </>
  );
}

function MeetingDisclosure({ disclosure }) {
  const [showPolicy, setShowPolicy] = useState(false);
  if (!disclosure) return null;
  return (
    <div className="meeting-disclosure" role="note">
      <p className="meeting-disclosure-anon">
        {disclosure.is_anonymous ? "This is an anonymous meeting" : "This meeting is not anonymous"}
        <button
          type="button"
          className="meeting-disclosure-help"
          aria-label="What does this mean?"
          aria-expanded={showPolicy}
          onClick={() => setShowPolicy((v) => !v)}
        >
          ?
        </button>
      </p>
      {showPolicy && <p className="meeting-disclosure-policy">{disclosure.anonymity_policy}</p>}
      <p>{disclosure.text}</p>
    </div>
  );
}

function ParticipantInfoForm({
  slide,
  values,
  onChange,
  onSubmit,
  submitting,
  error,
  submitLabel = "Continue",
}) {
  const fields = slide.participant_fields || [];

  return (
    <form onSubmit={onSubmit} className="resource-form">
      <MeetingDisclosure disclosure={slide.disclosure} />
      {fields.length === 0 && (
        <p className="resource-note">Tap Continue when you're ready to begin.</p>
      )}
      {fields.map((field) => (
        <label key={field.key} className="resource-field">
          <span>
            {field.label}
            {field.required ? " *" : ""}
          </span>
          {(field.field_type === "text" || !field.field_type) && (
            <input
              type="text"
              value={values[field.key] || ""}
              onChange={(e) => onChange(field.key, e.target.value)}
              required={field.required}
            />
          )}
          {field.field_type === "textarea" && (
            <textarea
              rows={4}
              value={values[field.key] || ""}
              onChange={(e) => onChange(field.key, e.target.value)}
              required={field.required}
            />
          )}
          {field.field_type === "single_select" && (
            <select
              value={values[field.key] || ""}
              onChange={(e) => onChange(field.key, e.target.value)}
              required={field.required}
            >
              <option value="">Select...</option>
              {(field.options || []).map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          )}
          {field.field_type === "multi_select" && (
            <div className="meeting-multi-select">
              {(field.options || []).map((opt) => {
                const selected = (values[field.key] || []).includes(opt);
                return (
                  <label key={opt} className="meeting-check-option">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={(e) => {
                        const current = values[field.key] || [];
                        const next = e.target.checked
                          ? [...current, opt]
                          : current.filter((v) => v !== opt);
                        onChange(field.key, next);
                      }}
                    />
                    {opt}
                  </label>
                );
              })}
            </div>
          )}
        </label>
      ))}
      {error && <p className="landing-code-error">{error}</p>}
      <button type="submit" className="landing-code-button" disabled={submitting}>
        {submitting ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}

function SelfPacedFinishPanel({
  allSlidesComplete,
  responsesFinalized,
  submitting,
  finalizeError,
  onFinalize,
}) {
  if (responsesFinalized) {
    return (
      <div className="meeting-self-paced-finish meeting-self-paced-finish--done">
        <h2>Thank you</h2>
        <p>
          Your answers have been submitted. You can leave this page or use the slide buttons
          above to review what you sent.
        </p>
      </div>
    );
  }
  if (!allSlidesComplete) return null;
  return (
    <div className="meeting-self-paced-finish">
      <p className="resource-note">
        You have visited every slide. Review your answers if you like, then submit when you
        are ready.
      </p>
      {finalizeError && <p className="landing-code-error">{finalizeError}</p>}
      <button
        type="button"
        className="landing-code-button meeting-self-paced-finish-btn"
        disabled={submitting}
        onClick={onFinalize}
      >
        {submitting ? "Submitting…" : "Finish and submit answers"}
      </button>
    </div>
  );
}

function QuestionForm({
  slide,
  responseText,
  selectedOptions,
  onTextChange,
  onOptionsChange,
  onSubmit,
  submitting,
  error,
  alreadyAnswered,
  allowRevisions = false,
  saveProgressLabel = "Save and continue",
}) {
  if (alreadyAnswered && !allowRevisions) {
    return (
      <p className="resource-note">
        You submitted a response for this slide. Waiting for the organizer to advance.
      </p>
    );
  }

  const revising = alreadyAnswered && allowRevisions;

  const isStandard = slide.slide_type === "standard";
  const isChoice =
    isStandard &&
    ["single_choice", "multi_choice"].includes(slide.question_format);

  return (
    <form onSubmit={onSubmit} className="resource-form">
      {revising && (
        <p className="resource-note">
          Update your answer below, then use <strong>{saveProgressLabel}</strong> to move
          forward.
        </p>
      )}
      {isChoice ? (
        <div className="resource-field">
          {(slide.choices || []).map((opt) => (
            <label key={opt} className="meeting-check-option">
              <input
                type={slide.question_format === "single_choice" ? "radio" : "checkbox"}
                name={`slide-${slide.id}`}
                checked={selectedOptions.includes(opt)}
                onChange={(e) => {
                  if (slide.question_format === "single_choice") {
                    onOptionsChange([opt]);
                  } else if (e.target.checked) {
                    onOptionsChange([...selectedOptions, opt]);
                  } else {
                    onOptionsChange(selectedOptions.filter((v) => v !== opt));
                  }
                }}
              />
              {opt}
            </label>
          ))}
        </div>
      ) : (
        <label className="resource-field">
          <span>Your response</span>
          <textarea
            required
            value={responseText}
            onChange={(e) => onTextChange(e.target.value)}
            rows={5}
          />
        </label>
      )}
      {error && <p className="landing-code-error">{error}</p>}
      <button type="submit" className="landing-code-button" disabled={submitting}>
        {submitting
          ? "Saving..."
          : allowRevisions
            ? saveProgressLabel
            : "Submit response"}
      </button>
    </form>
  );
}

export default function MeetingPage() {
  const { id } = useParams();

  const [meeting, setMeeting] = useState(null);
  const [session, setSession] = useState(null);
  const [participant, setParticipant] = useState(() => getMeetingParticipant(id));
  const [completedSlideIds, setCompletedSlideIds] = useState([]);
  const [privateCode, setPrivateCode] = useState("");
  const [profileValues, setProfileValues] = useState({});
  const [responseText, setResponseText] = useState("");
  const [selectedOptions, setSelectedOptions] = useState([]);
  const [issueItems, setIssueItems] = useState([]);
  const [viewingSlideId, setViewingSlideId] = useState(null);
  const [pageError, setPageError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [responsesFinalized, setResponsesFinalized] = useState(false);
  const [finalizeError, setFinalizeError] = useState("");
  const [finalizing, setFinalizing] = useState(false);
  const [showLiveResults, setShowLiveResults] = useState(false);

  const selfPaced = !!meeting?.allow_self_paced;
  const activeSlides = (meeting?.slides || [])
    .filter((s) => s.is_active !== false)
    .slice()
    .sort((a, b) => a.order - b.order);

  const loadSession = useCallback(async () => {
    const res = await api.get(`/api/meetings/${id}/session/`);
    setSession(res.data);
    return res.data;
  }, [id]);

  const loadMeeting = useCallback(async () => {
    const res = await api.get(`/api/meetings/${id}/`);
    setMeeting(res.data);
    return res.data;
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await Promise.all([loadMeeting(), loadSession()]);
      } catch (err) {
        if (!cancelled) {
          setPageError(err.response?.data?.detail || "Could not load meeting.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, loadMeeting, loadSession]);

  useEffect(() => {
    if (loading) return undefined;
    const interval = setInterval(() => {
      loadSession().catch(() => {});
    }, POLL_MS);
    return () => clearInterval(interval);
  }, [loading, loadSession]);

  useEffect(() => {
    if (!session || !participant?.session_id) return;
    if (session.id !== participant.session_id) {
      clearMeetingParticipant(id);
      setParticipant(null);
      setCompletedSlideIds([]);
    }
  }, [session?.id, participant?.session_id, id]);

  useEffect(() => {
    if (!participant?.attendance_id || !session) return;
    if (!["live", "paused"].includes(session.status)) return;

    api
      .post(`/api/meetings/${id}/join/`, {
        attendance_id: participant.attendance_id,
        private_code: privateCode,
      })
      .then((res) => {
        setCompletedSlideIds(res.data.completed_slide_ids || []);
        setResponsesFinalized(!!res.data.responses_finalized);
        setSession(res.data.session);
        if (res.data.session?.id) {
          saveMeetingParticipant(id, {
            ...participant,
            session_id: res.data.session.id,
          });
        }
      })
      .catch(() => {});
  }, [id, participant?.attendance_id, session?.status]);

  useEffect(() => {
    if (selfPaced) return;
    setResponseText("");
    setSelectedOptions([]);
    setIssueItems([]);
    setProfileValues({});
    setActionError("");
  }, [session?.current_slide?.id, selfPaced]);

  useEffect(() => {
    if (!selfPaced || !participant?.attendance_id || !viewingSlideId) return undefined;
    let cancelled = false;
    setResponseText("");
    setSelectedOptions([]);
    setIssueItems([]);
    setProfileValues({});
    setActionError("");
    api
      .get(`/api/meetings/${id}/participant-slide/`, {
        params: {
          attendance_id: participant.attendance_id,
          slide_id: viewingSlideId,
        },
      })
      .then((res) => {
        if (cancelled) return;
        const data = res.data || {};
        if (Array.isArray(data.issues)) {
          setIssueItems(
            data.issues.map((issue, index) => ({
              id: `issue-${viewingSlideId}-${index}`,
              text: issue.text,
            }))
          );
        } else if (data.fields) {
          setProfileValues(data.fields);
        } else {
          if (data.raw_response !== undefined) {
            setResponseText(data.raw_response);
          }
          if (Array.isArray(data.selected_options)) {
            setSelectedOptions(data.selected_options);
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selfPaced, participant?.attendance_id, viewingSlideId, id]);

  const needsLogin =
    meeting &&
    ["semi_public", "private"].includes(meeting.access_mode) &&
    !ensureValidSession();

  const sessionLive = session && ["live", "paused"].includes(session.status);
  const sessionPaused = session?.status === "paused";
  const sessionEnded = session?.status === "ended";

  const hostSlideId = session?.current_slide?.id || session?.current_slide_id;
  const hostSlide =
    activeSlides.find((s) => s.id === hostSlideId) || session?.current_slide || null;

  // Self-paced: stay on disclosure until done, then local navigation.
  // Organizer-paced: follow host current slide.
  useEffect(() => {
    if (!selfPaced || !activeSlides.length) return;
    const disclosure = activeSlides.find((s) => s.slide_type === "participant_info");
    if (disclosure && !completedSlideIds.includes(disclosure.id)) {
      setViewingSlideId(disclosure.id);
      return;
    }
    if (viewingSlideId && activeSlides.some((s) => s.id === viewingSlideId)) return;
    const next = activeSlides.find((s) => !completedSlideIds.includes(s.id));
    setViewingSlideId(next?.id || activeSlides[activeSlides.length - 1]?.id || null);
  }, [selfPaced, activeSlides, completedSlideIds, viewingSlideId]);

  const currentSlide = selfPaced
    ? activeSlides.find((s) => s.id === viewingSlideId) || null
    : hostSlide;

  const alreadyAnswered =
    currentSlide && completedSlideIds.includes(currentSlide.id);

  const markCompleteAndAdvance = (slideId) => {
    setCompletedSlideIds((prev) => {
      const next = prev.includes(slideId) ? prev : [...prev, slideId];
      if (selfPaced) {
        const done = new Set(next);
        const idx = activeSlides.findIndex((s) => s.id === slideId);
        const following = activeSlides.slice(idx + 1).find((s) => !done.has(s.id));
        const anyLeft = activeSlides.find((s) => !done.has(s.id));
        setViewingSlideId((following || anyLeft || null)?.id ?? null);
      }
      return next;
    });
  };

  const allSlidesComplete =
    selfPaced &&
    activeSlides.length > 0 &&
    activeSlides.every((s) => completedSlideIds.includes(s.id));

  const canEditSelfPaced = selfPaced && !responsesFinalized;

  const handleFinalize = async () => {
    setFinalizeError("");
    setFinalizing(true);
    try {
      await api.post(`/api/meetings/${id}/finalize/`, {
        attendance_id: participant.attendance_id,
      });
      setResponsesFinalized(true);
    } catch (err) {
      setFinalizeError(
        err.response?.data?.detail || "Could not submit your answers. Try again."
      );
    } finally {
      setFinalizing(false);
    }
  };

  const handleJoin = async (e) => {
    e?.preventDefault();
    setActionError("");
    setJoining(true);
    try {
      const payload = { private_code: privateCode };
      if (participant?.attendance_id) {
        payload.attendance_id = participant.attendance_id;
      }
      const res = await api.post(`/api/meetings/${id}/join/`, payload);
      const record = {
        attendance_id: res.data.attendance_id,
        participant_id: res.data.participant_id,
        is_anonymous: res.data.is_anonymous,
        session_id: res.data.session?.id,
      };
      saveMeetingParticipant(id, record);
      setParticipant(record);
      setCompletedSlideIds(res.data.completed_slide_ids || []);
      setResponsesFinalized(!!res.data.responses_finalized);
      setSession(res.data.session);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) {
        setActionError(detail || "Meeting has not started yet.");
      } else if (err.response?.status === 403) {
        setActionError(detail || "You cannot join this meeting.");
      } else {
        setActionError(detail || "Could not join meeting.");
      }
    } finally {
      setJoining(false);
    }
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setActionError("");
    setSubmitting(true);
    try {
      await api.post(`/api/meetings/${id}/profile/`, {
        attendance_id: participant.attendance_id,
        slide_id: currentSlide.id,
        fields: profileValues,
      });
      if (!completedSlideIds.includes(currentSlide.id)) {
        setProfileValues({});
      }
      markCompleteAndAdvance(currentSlide.id);
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not save profile.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleIssueSubmit = async (issues) => {
    setActionError("");
    setSubmitting(true);
    try {
      await api.post(`/api/meetings/${id}/respond/`, {
        attendance_id: participant.attendance_id,
        slide_id: currentSlide.id,
        issues: issues.map((issue, index) => ({
          text: issue.text,
          importance_order: index + 1,
        })),
      });
      if (!completedSlideIds.includes(currentSlide.id)) {
        setIssueItems([]);
      }
      markCompleteAndAdvance(currentSlide.id);
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not submit issues.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRespond = async (e) => {
    e.preventDefault();
    setActionError("");
    setSubmitting(true);
    try {
      await api.post(`/api/meetings/${id}/respond/`, {
        attendance_id: participant.attendance_id,
        slide_id: currentSlide.id,
        raw_response: responseText,
        selected_options: selectedOptions,
      });
      if (!completedSlideIds.includes(currentSlide.id)) {
        setResponseText("");
        setSelectedOptions([]);
      }
      markCompleteAndAdvance(currentSlide.id);
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not submit response.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleContentContinue = async () => {
    setActionError("");
    setSubmitting(true);
    try {
      await api.post(`/api/meetings/${id}/respond/`, {
        attendance_id: participant.attendance_id,
        slide_id: currentSlide.id,
        raw_response: "",
      });
      markCompleteAndAdvance(currentSlide.id);
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not continue.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLeave = async () => {
    if (!participant) return;
    try {
      await api.post(`/api/meetings/${id}/leave/`, {
        attendance_id: participant.attendance_id,
      });
    } catch {
      /* ignore */
    }
    clearMeetingParticipant(id);
    setParticipant(null);
    setCompletedSlideIds([]);
    setResponsesFinalized(false);
  };

  if (loading) {
    return (
      <div className="resource-page">
        <p>Loading meeting...</p>
      </div>
    );
  }

  if (pageError || !meeting) {
    return (
      <div className="resource-page">
        <Link to="/" className="resource-back">
          &larr; Back to home
        </Link>
        <p>{pageError || "Meeting not found."}</p>
      </div>
    );
  }

  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>{meeting.title}</h1>
      {meeting.description && <p>{meeting.description}</p>}

      <ul className="resource-meta">
        <li>
          <strong>Organization:</strong> {meeting.organization_name}
        </li>
        <li>
          <strong>Session:</strong> {session?.status || meeting.status}
        </li>
        {session && (
          <li>
            <strong>In room:</strong> {session.attendance_count ?? 0}
          </li>
        )}
        {participant?.is_anonymous && participant?.participant_id && (
          <li>
            <strong>Your ID:</strong> {participant.participant_id.slice(0, 8)}…
          </li>
        )}
      </ul>

      {needsLogin && (
        <div className="meeting-gate">
          <p>Login is required to join this meeting.</p>
          <Link to="/" className="landing-code-button meeting-gate-link">
            Go to login
          </Link>
        </div>
      )}

      {!needsLogin && sessionEnded && (
        <div className="meeting-waiting">
          <h2>Meeting ended</h2>
          <p>This meeting session has ended. Thank you for participating.</p>
        </div>
      )}

      {!needsLogin && !sessionLive && !sessionEnded && (
        <div className="meeting-waiting">
          <h2>Waiting for the organizer</h2>
          <p>
            This meeting has not started yet.
            {meeting.scheduled_start_at && (
              <>
                {" "}
                Scheduled for{" "}
                {new Date(meeting.scheduled_start_at).toLocaleString()}.
              </>
            )}
          </p>
          <p className="resource-note">This page refreshes automatically.</p>
        </div>
      )}

      {!needsLogin && sessionLive && !participant && (
        <div className="meeting-join">
          <h2>Join meeting</h2>
          {meeting.access_mode === "private" && (
            <label className="resource-field">
              <span>Private meeting code</span>
              <input
                type="text"
                value={privateCode}
                onChange={(e) => setPrivateCode(e.target.value.toUpperCase())}
                required
              />
            </label>
          )}
          {actionError && <p className="landing-code-error">{actionError}</p>}
          <button
            type="button"
            className="landing-code-button"
            onClick={handleJoin}
            disabled={joining}
          >
            {joining ? "Joining..." : "Join meeting"}
          </button>
        </div>
      )}

      {!needsLogin && sessionLive && participant && sessionPaused && (
        <div className="meeting-waiting">
          <h2>Meeting paused</h2>
          <p>The organizer has paused the meeting. Please wait.</p>
        </div>
      )}

      {!needsLogin && sessionLive && participant && currentSlide && !sessionPaused && (
        <section className="meeting-slide">
          {selfPaced && (
            <div className="meeting-self-paced-nav">
              <p className="resource-meta">
                Self-paced · slide{" "}
                {Math.max(1, activeSlides.findIndex((s) => s.id === currentSlide.id) + 1)} of{" "}
                {activeSlides.length}
              </p>
              <div className="dashboard-actions">
                {activeSlides.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`dashboard-btn${s.id === currentSlide.id ? " dashboard-btn--primary" : ""}`}
                    disabled={
                      s.slide_type !== "participant_info" &&
                      activeSlides.some(
                        (d) =>
                          d.slide_type === "participant_info" &&
                          !completedSlideIds.includes(d.id)
                      )
                    }
                    onClick={() => setViewingSlideId(s.id)}
                  >
                    {s.order + 1 || ""}{" "}
                    {(s.title || s.prompt || s.slide_type).slice(0, 24)}
                    {completedSlideIds.includes(s.id) ? " ✓" : ""}
                  </button>
                ))}
              </div>
            </div>
          )}

          {selfPaced && responsesFinalized && (
            <SelfPacedFinishPanel
              allSlidesComplete={allSlidesComplete}
              responsesFinalized
              submitting={finalizing}
              finalizeError={finalizeError}
              onFinalize={handleFinalize}
            />
          )}

          {currentSlide.slide_type !== "content" && <SlidePrompt slide={currentSlide} />}

          {responsesFinalized && selfPaced ? (
            <p className="resource-note">
              Your answers for this slide were submitted. Use another slide button above to
              review.
            </p>
          ) : (
            <>
              {currentSlide.slide_type === "participant_info" &&
                (alreadyAnswered && !selfPaced ? (
                  <p className="resource-note">
                    Profile saved. Waiting for the organizer to advance.
                  </p>
                ) : (
                  <ParticipantInfoForm
                    slide={currentSlide}
                    values={profileValues}
                    onChange={(key, val) =>
                      setProfileValues((prev) => ({ ...prev, [key]: val }))
                    }
                    onSubmit={handleProfileSubmit}
                    submitting={submitting}
                    error={actionError}
                    submitLabel={canEditSelfPaced ? "Save and continue" : "Continue"}
                  />
                ))}

              {currentSlide.slide_type === "content" && (
                <>
                  <ContentBlock
                    title={currentSlide.title}
                    content={currentSlide.content || currentSlide.config}
                  />
                  {alreadyAnswered && !selfPaced ? (
                    <p className="resource-note">Waiting for the organizer to advance.</p>
                  ) : (
                    <button
                      type="button"
                      className="landing-code-button"
                      disabled={submitting}
                      onClick={handleContentContinue}
                    >
                      {submitting
                        ? "Saving…"
                        : canEditSelfPaced
                          ? "Save and continue"
                          : "Continue"}
                    </button>
                  )}
                  {actionError && <p className="landing-code-error">{actionError}</p>}
                </>
              )}

              {currentSlide.slide_type === "standard" && (
                <QuestionForm
                  slide={currentSlide}
                  responseText={responseText}
                  selectedOptions={selectedOptions}
                  onTextChange={setResponseText}
                  onOptionsChange={setSelectedOptions}
                  onSubmit={handleRespond}
                  submitting={submitting}
                  error={actionError}
                  alreadyAnswered={alreadyAnswered}
                  allowRevisions={canEditSelfPaced}
                />
              )}

              {["issue_card", "political_issue_card"].includes(currentSlide.slide_type) && (
                <IssueCardForm
                  issues={issueItems}
                  onChange={setIssueItems}
                  onSubmit={handleIssueSubmit}
                  submitting={submitting}
                  error={actionError}
                  alreadyAnswered={alreadyAnswered}
                  allowRevisions={canEditSelfPaced}
                />
              )}
            </>
          )}

          {selfPaced && !responsesFinalized && (
            <SelfPacedFinishPanel
              allSlidesComplete={allSlidesComplete}
              responsesFinalized={false}
              submitting={finalizing}
              finalizeError={finalizeError}
              onFinalize={handleFinalize}
            />
          )}
        </section>
      )}

      {!needsLogin && sessionLive && participant && !currentSlide && !sessionPaused && (
        <>
          {selfPaced ? (
            <SelfPacedFinishPanel
              allSlidesComplete={allSlidesComplete}
              responsesFinalized={responsesFinalized}
              submitting={finalizing}
              finalizeError={finalizeError}
              onFinalize={handleFinalize}
            />
          ) : (
            <p className="resource-note">No active slide. Waiting for the organizer.</p>
          )}
        </>
      )}

      {!needsLogin && participant && meeting.live_results_for_participants && (sessionLive || sessionEnded) && (
        <div className="live-results-toggle">
          <button
            type="button"
            className="dashboard-btn"
            aria-expanded={showLiveResults}
            onClick={() => setShowLiveResults((v) => !v)}
          >
            {showLiveResults ? "Hide live results" : "Show live results"}
            {` (${(session?.participant_results_released_slide_ids || []).length} shared)`}
          </button>
          {showLiveResults && (
            <LiveResultsPanel
              kind="meeting"
              resourceId={id}
              identity={participant.attendance_id}
              showOpenLink
            />
          )}
        </div>
      )}

      {participant && (
        <button type="button" className="meeting-leave-btn" onClick={handleLeave}>
          Leave meeting
        </button>
      )}
    </div>
  );
}
