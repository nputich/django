import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { ensureValidSession } from "../auth";
import IssueCardForm from "../components/IssueCardForm";
import {
  clearMeetingParticipant,
  getMeetingParticipant,
  saveMeetingParticipant,
} from "../meetingParticipant";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

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

function ParticipantInfoForm({ slide, values, onChange, onSubmit, submitting, error }) {
  const fields = slide.participant_fields || [];

  return (
    <form onSubmit={onSubmit} className="resource-form">
      {fields.map((field) => (
        <label key={field.key} className="resource-field">
          <span>
            {field.label}
            {field.required ? " *" : ""}
          </span>
          {field.field_type === "text" && (
            <input
              type="text"
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
        {submitting ? "Saving..." : "Continue"}
      </button>
    </form>
  );
}

function QuestionForm({ slide, responseText, selectedOptions, onTextChange, onOptionsChange, onSubmit, submitting, error, alreadyAnswered }) {
  if (alreadyAnswered) {
    return (
      <p className="resource-note">
        You submitted a response for this slide. Waiting for the organizer to advance.
      </p>
    );
  }

  const isStandard = slide.slide_type === "standard";
  const isChoice =
    isStandard &&
    ["single_choice", "multi_choice"].includes(slide.question_format);

  return (
    <form onSubmit={onSubmit} className="resource-form">
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
        {submitting ? "Submitting..." : "Submit response"}
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
  const [pageError, setPageError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [submitting, setSubmitting] = useState(false);

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
    setResponseText("");
    setSelectedOptions([]);
    setIssueItems([]);
    setActionError("");
  }, [session?.current_slide?.id]);

  const needsLogin =
    meeting &&
    ["semi_public", "private"].includes(meeting.access_mode) &&
    !ensureValidSession();

  const sessionLive = session && ["live", "paused"].includes(session.status);
  const sessionPaused = session?.status === "paused";
  const sessionEnded = session?.status === "ended";
  const currentSlide = session?.current_slide;
  const alreadyAnswered =
    currentSlide && completedSlideIds.includes(currentSlide.id);

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
      setCompletedSlideIds((prev) =>
        prev.includes(currentSlide.id) ? prev : [...prev, currentSlide.id]
      );
      setProfileValues({});
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
      setCompletedSlideIds((prev) =>
        prev.includes(currentSlide.id) ? prev : [...prev, currentSlide.id]
      );
      setIssueItems([]);
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
      setCompletedSlideIds((prev) =>
        prev.includes(currentSlide.id) ? prev : [...prev, currentSlide.id]
      );
    } catch (err) {
      setActionError(err.response?.data?.detail || "Could not submit response.");
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
          <SlidePrompt slide={currentSlide} />

          {currentSlide.slide_type === "participant_info" && (
            alreadyAnswered ? (
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
            />
            )
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
            />
          )}

          {!["participant_info", "standard", "issue_card", "political_issue_card"].includes(
            currentSlide.slide_type
          ) && (
            <p className="resource-note">Unsupported slide type.</p>
          )}
        </section>
      )}

      {!needsLogin && sessionLive && participant && !currentSlide && !sessionPaused && (
        <p className="resource-note">No active slide. Waiting for the organizer.</p>
      )}

      {participant && (
        <button type="button" className="meeting-leave-btn" onClick={handleLeave}>
          Leave meeting
        </button>
      )}
    </div>
  );
}
