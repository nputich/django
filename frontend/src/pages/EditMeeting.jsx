import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import MeetingSlideEditor, {
  emptyIssueSlide,
  emptyParticipantInfoSlide,
  emptyStandardSlide,
  slideFromApi,
  slideToPayload,
} from "../components/MeetingSlideEditor";
import "../styles/Dashboard.css";

function toDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function validateSlides(slides) {
  for (let index = 0; index < slides.length; index += 1) {
    const slide = slides[index];
    const label = `Slide ${index + 1}`;

    if (slide.slide_type === "standard") {
      if (!slide.prompt.trim() && !slide.title.trim()) {
        return `${label}: add a prompt or title.`;
      }
      if (
        ["single_choice", "multi_choice"].includes(slide.question_format) &&
        slide.choices.filter(Boolean).length < 2
      ) {
        return `${label}: choice questions need at least two options.`;
      }
    }

    if (
      slide.slide_type === "issue_card" ||
      slide.slide_type === "political_issue_card"
    ) {
      if (!slide.prompt.trim() && !slide.title.trim()) {
        return `${label}: add a prompt or title.`;
      }
    }

    if (slide.slide_type === "participant_info") {
      if (!slide.fields.length) {
        return `${label}: add at least one participant question.`;
      }
      for (const field of slide.fields) {
        if (!field.label.trim()) {
          return `${label}: each participant question needs a label.`;
        }
        if (
          ["single_select", "multi_select"].includes(field.field_type) &&
          (field.options || []).filter(Boolean).length < 2
        ) {
          return `${label}: "${field.label}" needs at least two options.`;
        }
      }
    }
  }
  return "";
}

export default function EditMeeting() {
  const { slug, id } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [allowStartEarly, setAllowStartEarly] = useState(false);
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [aiMode, setAiMode] = useState("none");
  const [slides, setSlides] = useState([]);
  const [expandedIndex, setExpandedIndex] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/api/organizations/${slug}/meetings/${id}/`);
        if (cancelled) return;
        const m = res.data;
        setMeeting(m);
        setTitle(m.title || "");
        setDescription(m.description || "");
        setScheduledStartAt(toDatetimeLocal(m.scheduled_start_at));
        setAllowStartEarly(!!m.allow_start_early);
        setIsAnonymous(!!m.is_anonymous);
        setAiMode(m.ai_mode || "none");
        const loadedSlides = (m.slides || [])
          .slice()
          .sort((a, b) => a.order - b.order)
          .map(slideFromApi);
        setSlides(loadedSlides);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not load meeting.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, id]);

  const updateSlide = (index, nextSlide) => {
    setSlides((prev) => prev.map((slide, i) => (i === index ? nextSlide : slide)));
  };

  const addSlide = (slideType) => {
    let nextSlide = emptyStandardSlide();
    if (slideType === "participant_info") {
      nextSlide = emptyParticipantInfoSlide();
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

  const removeSlide = (index) => {
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
    setSuccess("");

    if (!slides.length) {
      setError("Add at least one slide.");
      return;
    }

    const slideError = validateSlides(slides);
    if (slideError) {
      setError(slideError);
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.patch(`/api/organizations/${slug}/meetings/${id}/`, {
        title: title.trim(),
        description: description.trim(),
        scheduled_start_at: scheduledStartAt
          ? new Date(scheduledStartAt).toISOString()
          : null,
        allow_start_early: allowStartEarly,
        is_anonymous: isAnonymous,
        ai_mode: aiMode,
        slides: slides.map((slide, index) => slideToPayload(slide, index + 1)),
      });

      setMeeting(res.data);
      setSlides(
        (res.data.slides || [])
          .slice()
          .sort((a, b) => a.order - b.order)
          .map(slideFromApi)
      );
      setExpandedIndex(null);
      setSuccess("Meeting updated.");
      setTimeout(() => navigate(`/dashboard/${slug}`), 2000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          JSON.stringify(err.response?.data) ||
          "Could not update meeting."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p>Loading meeting...</p>
        </main>
      </div>
    );
  }

  if (!meeting) {
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

  const isLive = ["live", "paused"].includes(meeting.status);

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Edit meeting</h1>
          <p>
            {meeting.title} · {meeting.status}
            {meeting.community_code && (
              <>
                {" "}
                · Code <span className="dashboard-code">{meeting.community_code}</span>
              </>
            )}
          </p>
        </div>

        {isLive && (
          <p className="dashboard-error">
            This meeting is live. You can update settings here, but to add slides during
            the session use{" "}
            <Link to={`/dashboard/${slug}/meetings/${id}/host`}>Host controls</Link>.
          </p>
        )}

        {success && <div className="dashboard-success">{success}</div>}

        <form className="dashboard-form" onSubmit={handleSubmit}>
          <div className="dashboard-field">
            <label htmlFor="edit-meeting-title">Title</label>
            <input
              id="edit-meeting-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="edit-meeting-description">Description</label>
            <textarea
              id="edit-meeting-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="edit-meeting-start">Scheduled start</label>
            <input
              id="edit-meeting-start"
              type="datetime-local"
              value={scheduledStartAt}
              onChange={(e) => setScheduledStartAt(e.target.value)}
            />
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

          <div className="dashboard-field">
            <label htmlFor="edit-meeting-ai">AI mode</label>
            <select
              id="edit-meeting-ai"
              value={aiMode}
              onChange={(e) => setAiMode(e.target.value)}
            >
              <option value="none">No AI</option>
              <option value="self_hosted">Self-hosted AI</option>
              <option value="paid">Paid AI model</option>
            </select>
          </div>

          {!isLive && (
            <div className="dashboard-section">
              <div className="dashboard-section-header">
                <h2>Slides ({slides.length})</h2>
                <div className="dashboard-section-actions">
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
                    onClick={() => addSlide("participant_info")}
                  >
                    + Participant info
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

              {slides.length === 0 ? (
                <p className="dashboard-empty">No slides yet. Add one above.</p>
              ) : (
                slides.map((slide, index) => (
                  <MeetingSlideEditor
                    key={slide.id || `new-${index}`}
                    slide={slide}
                    order={index + 1}
                    expanded={expandedIndex === index}
                    onToggleExpand={() =>
                      setExpandedIndex((current) => (current === index ? null : index))
                    }
                    onChange={(nextSlide) => updateSlide(index, nextSlide)}
                    onDelete={() => removeSlide(index)}
                    canDelete={slides.length > 1}
                  />
                ))
              )}
            </div>
          )}

          {isLive && slides.length > 0 && (
            <div className="dashboard-card">
              <h2>Current slides ({slides.length})</h2>
              <p className="dashboard-meta">
                Slide edits are locked while the meeting is live. End the meeting to edit
                slides here, or add slides from host controls during the session.
              </p>
              <ul className="dashboard-list">
                {slides.map((slide, index) => (
                  <li key={slide.id || index} className="dashboard-list-item">
                    <div>
                      <strong>Slide {index + 1}</strong>
                      <p className="dashboard-meta">{slide.prompt || slide.title}</p>
                      {slide.slide_type === "standard" &&
                        ["single_choice", "multi_choice"].includes(slide.question_format) && (
                          <p className="dashboard-meta">
                            Options: {(slide.choices || []).join(", ") || "None"}
                          </p>
                        )}
                      {slide.slide_type === "participant_info" && (
                        <p className="dashboard-meta">
                          {(slide.fields || [])
                            .map((field) => field.label)
                            .join(", ") || "No participant questions"}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && <p className="dashboard-error">{error}</p>}

          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting || isLive}
          >
            {submitting ? "Saving..." : "Save changes"}
          </button>
        </form>
      </main>
    </div>
  );
}
