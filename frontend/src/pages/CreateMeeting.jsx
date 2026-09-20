import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import MeetingSlideEditor, {
  emptyIssueSlide,
  emptyParticipantInfoSlide,
  emptyContentSlide,
  emptyStandardSlide,
  validateSlidesForSave,
  slideToPayload,
} from "../components/MeetingSlideEditor";
import MeetingSharingFields from "../components/MeetingSharingFields";
import ReuseQuestionsPanel from "../components/ReuseQuestionsPanel";
import { normalizeAccessCode } from "../accessCode";
import "../styles/Dashboard.css";

export default function CreateMeeting() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [accessMode, setAccessMode] = useState("public");
  const [accessCode, setAccessCode] = useState("");
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [scheduledEndAt, setScheduledEndAt] = useState("");
  const [location, setLocation] = useState("");
  const [allowStartEarly, setAllowStartEarly] = useState(false);
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [allowSelfPaced, setAllowSelfPaced] = useState(false);
  const [aiMode, setAiMode] = useState("none");
  const [resultsVisible, setResultsVisible] = useState(false);
  const [minutesCreator, setMinutesCreator] = useState("organizer_only");
  const [aggregateNotice, setAggregateNotice] = useState(true);
  const [shareWith, setShareWith] = useState([]);
  const [slides, setSlides] = useState([
    emptyParticipantInfoSlide(),
    emptyStandardSlide(),
  ]);
  const [expandedIndex, setExpandedIndex] = useState(0);
  const [codeStatus, setCodeStatus] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [entitlementBlocked, setEntitlementBlocked] = useState(false);

  const slideValidationError = validateSlidesForSave(slides, expandedIndex);
  const canSave = !slideValidationError && !entitlementBlocked;

  useEffect(() => {
    api
      .get(`/api/organizations/${slug}/dashboard/`)
      .then((res) => {
        if (res.data.capabilities && !res.data.capabilities.create_meetings) {
          setEntitlementBlocked(true);
        }
      })
      .catch(() => {});
  }, [slug]);

  const checkCode = useCallback(async (code) => {
    if (!code.trim()) {
      setCodeStatus(null);
      return;
    }
    try {
      const res = await api.get("/api/access-codes/check/", {
        params: { code: code.trim(), type: "meeting" },
      });
      setCodeStatus(res.data);
    } catch (err) {
      setCodeStatus({
        available: false,
        detail: err.response?.data?.detail || "Could not check code.",
      });
    }
  }, []);

  const updateSlide = (index, nextSlide) => {
    setSlides((prev) => prev.map((slide, i) => (i === index ? nextSlide : slide)));
  };

  const addSlide = (slideType) => {
    let nextSlide = emptyStandardSlide();
    if (slideType === "participant_info") {
      nextSlide = emptyParticipantInfoSlide();
    } else if (slideType === "content") {
      nextSlide = emptyContentSlide();
    } else if (slideType === "issue_card") {
      nextSlide = emptyIssueSlide("issue_card");
    } else if (slideType === "political_issue_card") {
      nextSlide = emptyIssueSlide("political_issue_card");
    }
    setSlides((prev) => {
      const next = [...prev, nextSlide];
      setExpandedIndex(next.length - 1);
      return next;
    });
  };

  const addReusedSlides = (reused) => {
    setSlides((prev) => [...prev, ...reused]);
    setExpandedIndex(null);
  };

  const removeSlide = (index) => {
    if (slides.length <= 1) return;
    if (!window.confirm("Delete this slide?")) return;
    setSlides((prev) => prev.filter((_, i) => i !== index));
    setExpandedIndex((current) => {
      if (current === null) return null;
      if (current === index) return null;
      if (current > index) return current - 1;
      return current;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess(null);

    if (!slides.length) {
      setError("Add at least one slide.");
      return;
    }

    const slideError = validateSlidesForSave(slides, expandedIndex);
    if (slideError) {
      setError(slideError);
      return;
    }

    setSubmitting(true);
    const payload = {
      title: title.trim(),
      description: description.trim(),
      location: location.trim(),
      access_mode: accessMode,
      access_code: accessCode.trim(),
      scheduled_start_at: scheduledStartAt
        ? new Date(scheduledStartAt).toISOString()
        : null,
      scheduled_end_at: scheduledEndAt
        ? new Date(scheduledEndAt).toISOString()
        : null,
      allow_start_early: allowStartEarly,
      is_anonymous: isAnonymous,
      allow_self_paced: allowSelfPaced,
      ai_mode: aiMode,
      results_visible_to_community: resultsVisible,
      minutes_creator: minutesCreator,
      aggregate_sharing_notice: aggregateNotice,
      share_with: shareWith.map((o) => o.slug),
      slides: slides.map((slide, index) => slideToPayload(slide, index + 1)),
    };

    try {
      const res = await api.post(`/api/organizations/${slug}/meetings/`, payload);
      setSuccess(res.data);
      setTimeout(() => navigate(`/dashboard/${slug}`), 2500);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          JSON.stringify(err.response?.data) ||
          "Could not create meeting."
      );
    } finally {
      setSubmitting(false);
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
          <h1>Create meeting</h1>
          <p>
            Schedule a structured meeting with slides. Customize demographic
            questions, then add discussion slides.
          </p>
        </div>

        {entitlementBlocked && (
          <div className="dashboard-card">
            <h2>Create a New Meeting</h2>
            <p>
              New meetings require communiBetter Starter or higher. Your previous
              meetings, responses, and reports remain available.
            </p>
            <div className="dashboard-actions">
              <Link to={`/dashboard/${slug}`} className="dashboard-btn">
                Back to dashboard
              </Link>
              <Link
                to={`/dashboard/${slug}/billing`}
                className="dashboard-btn dashboard-btn--primary"
              >
                View plans
              </Link>
            </div>
          </div>
        )}

        {success && (
          <div className="dashboard-success">
            <strong>Meeting created!</strong>
            <p>
              Community code:{" "}
              <span className="dashboard-code">{success.access_code.code}</span>
            </p>
            <p>Redirecting to dashboard...</p>
          </div>
        )}

        {!entitlementBlocked && !success && (
          <form className="dashboard-form" onSubmit={handleSubmit}>
            <div className="dashboard-field">
              <label htmlFor="meeting-title">Title</label>
              <input
                id="meeting-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-description">Description</label>
              <textarea
                id="meeting-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-start">Scheduled start</label>
              <input
                id="meeting-start"
                type="datetime-local"
                value={scheduledStartAt}
                onChange={(e) => setScheduledStartAt(e.target.value)}
              />
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-end">Expected end (optional)</label>
              <input
                id="meeting-end"
                type="datetime-local"
                value={scheduledEndAt}
                onChange={(e) => setScheduledEndAt(e.target.value)}
              />
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-location">Location</label>
              <input
                id="meeting-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Central Library, or online link notes"
              />
            </div>

            <div className="dashboard-field">
              <fieldset className="dashboard-fieldset">
                <legend>Results visibility</legend>
                <p className="dashboard-meta">
                  Allow participants/community members to view meeting results
                  after the meeting
                </p>
                <div className="dashboard-switch-row">
                  <span>{resultsVisible ? "ON" : "OFF"}</span>
                  <label className="dashboard-switch">
                    <input
                      type="checkbox"
                      role="switch"
                      checked={resultsVisible}
                      onChange={(e) => setResultsVisible(e.target.checked)}
                      aria-label="Allow participants to view meeting results after the meeting"
                    />
                    <span className="dashboard-switch-track" aria-hidden />
                  </label>
                </div>
              </fieldset>
            </div>

            <div className="dashboard-field">
              <fieldset className="dashboard-fieldset">
                <legend>Meeting minutes</legend>
                <p className="dashboard-meta">Who may create the meeting minutes?</p>
                <label className="dashboard-radio-row">
                  <input
                    type="radio"
                    name="minutes-creator"
                    checked={minutesCreator === "organizer_only"}
                    onChange={() => setMinutesCreator("organizer_only")}
                  />{" "}
                  Organizer only
                </label>
                <label className="dashboard-radio-row">
                  <input
                    type="radio"
                    name="minutes-creator"
                    checked={minutesCreator === "organizer_or_attendees"}
                    onChange={() => setMinutesCreator("organizer_or_attendees")}
                  />{" "}
                  Organizer or attendees
                </label>
              </fieldset>
            </div>

            <div className="dashboard-field dashboard-field--row">
              <label>
                <input
                  type="checkbox"
                  checked={allowStartEarly}
                  onChange={(e) => setAllowStartEarly(e.target.checked)}
                />{" "}
                Allow start early
              </label>
            </div>

            <div className="dashboard-field dashboard-field--row">
              <label>
                <input
                  type="checkbox"
                  checked={isAnonymous}
                  onChange={(e) => setIsAnonymous(e.target.checked)}
                />{" "}
                Anonymous meeting
              </label>
            </div>

            <div className="dashboard-field dashboard-field--row">
              <label>
                <input
                  type="checkbox"
                  checked={allowSelfPaced}
                  onChange={(e) => setAllowSelfPaced(e.target.checked)}
                />{" "}
                Allow self-paced answers (participants do not wait for the organizer to
                advance)
              </label>
            </div>

            <MeetingSharingFields
              orgSlug={slug}
              isAnonymous={isAnonymous}
              aggregateNotice={aggregateNotice}
              onAggregateNoticeChange={setAggregateNotice}
              pending={shareWith}
              onPendingChange={setShareWith}
            />

            <div className="dashboard-field">
              <label htmlFor="meeting-ai">AI mode</label>
              <select
                id="meeting-ai"
                value={aiMode}
                onChange={(e) => setAiMode(e.target.value)}
              >
                <option value="none">No AI</option>
                <option value="self_hosted">Self-hosted AI</option>
                <option value="paid">Paid AI model</option>
              </select>
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-access">Access mode</label>
              <select
                id="meeting-access"
                value={accessMode}
                onChange={(e) => setAccessMode(e.target.value)}
              >
                <option value="public">Public</option>
                <option value="semi_public">Semi-public (login required)</option>
                <option value="private">Private</option>
              </select>
            </div>

            <div className="dashboard-field">
              <label htmlFor="meeting-code">Community code (optional)</label>
              <input
                id="meeting-code"
                value={accessCode}
                onChange={(e) => {
                  setAccessCode(normalizeAccessCode(e.target.value));
                  setCodeStatus(null);
                }}
                onBlur={() => checkCode(accessCode)}
                placeholder="Leave blank to auto-generate"
              />
              <small>
                Direct-entry community code for this meeting. Org and survey codes
                work the same way for their resources.
              </small>
              {codeStatus && (
                <p
                  className={`dashboard-code-status ${
                    codeStatus.available
                      ? "dashboard-code-status--ok"
                      : "dashboard-code-status--bad"
                  }`}
                >
                  {codeStatus.available
                    ? `Available${codeStatus.normalized ? `: ${codeStatus.normalized}` : ""}`
                    : codeStatus.detail || "Not available"}
                </p>
              )}
            </div>

            <div className="dashboard-section">
              <div className="dashboard-section-header">
                <h2>Slides ({slides.length})</h2>
                <div className="dashboard-section-actions">
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addSlide("participant_info")}
                  >
                    + Demographic / about you
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addSlide("content")}
                  >
                    + Content (banner / video)
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addSlide("standard")}
                  >
                    + Standard
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addSlide("issue_card")}
                  >
                    + Issue card
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addSlide("political_issue_card")}
                  >
                    + Political issue
                  </button>
                </div>
              </div>
              <p className="dashboard-meta">
                The first slide is always the disclosure / about-you screen. Add free-text
                or multiple-choice demographic questions to it (zip code, neighborhood, age
                range, etc.), then add discussion slides.
              </p>

              <ReuseQuestionsPanel orgSlug={slug} onAdd={addReusedSlides} />

              {slides.map((slide, index) => (
                <MeetingSlideEditor
                  key={slide.clientId || `new-${index}`}
                  slide={slide}
                  order={index + 1}
                  expanded={expandedIndex === index}
                  onToggleExpand={() =>
                    setExpandedIndex((current) => (current === index ? null : index))
                  }
                  onChange={(nextSlide) => updateSlide(index, nextSlide)}
                  onDelete={() => removeSlide(index)}
                  canDelete={slides.length > 1 && slide.slide_type !== "participant_info"}
                  orgSlug={slug}
                />
              ))}
            </div>

            {slideValidationError && (
              <p className="dashboard-error">{slideValidationError}</p>
            )}

            {error && <p className="dashboard-error">{error}</p>}

            <button
              type="submit"
              className="dashboard-btn dashboard-btn--primary"
              disabled={submitting || !canSave}
              title={slideValidationError || undefined}
            >
              {submitting ? "Creating..." : "Create meeting"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
