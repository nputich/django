import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

function emptyStandardSlide() {
  return {
    slide_type: "standard",
    title: "",
    prompt: "",
    question_format: "text",
    choices: [],
    fields: [],
  };
}

function emptyIssueSlide(slideType) {
  return {
    slide_type: slideType,
    title: "",
    prompt:
      slideType === "political_issue_card"
        ? "Describe a policy issue that matters to you."
        : "Share a concern or suggestion.",
    question_format: "",
    choices: [],
    fields: [],
  };
}

function slideLabel(slide) {
  const type = slide.slide_type.replace(/_/g, " ");
  const text = slide.prompt || slide.title || "";
  return `#${slide.order} ${type}${text ? `: ${text.slice(0, 50)}` : ""}`;
}

function toDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
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
  const [newSlides, setNewSlides] = useState([emptyStandardSlide()]);
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

  const updateNewSlide = (index, field, value) => {
    setNewSlides((prev) =>
      prev.map((slide, i) => (i === index ? { ...slide, [field]: value } : slide))
    );
  };

  const addNewSlide = (slideType) => {
    if (slideType === "issue_card") {
      setNewSlides((prev) => [...prev, emptyIssueSlide("issue_card")]);
    } else if (slideType === "political_issue_card") {
      setNewSlides((prev) => [...prev, emptyIssueSlide("political_issue_card")]);
    } else {
      setNewSlides((prev) => [...prev, emptyStandardSlide()]);
    }
  };

  const removeNewSlide = (index) => {
    if (newSlides.length <= 1) return;
    setNewSlides((prev) => prev.filter((_, i) => i !== index));
  };

  const buildNewSlidePayloads = () =>
    newSlides.map((slide) => ({
      slide_type: slide.slide_type,
      title: slide.title.trim(),
      prompt: slide.prompt.trim(),
      question_format:
        slide.slide_type === "standard" ? slide.question_format : "",
      choices:
        slide.slide_type === "standard" &&
        ["single_choice", "multi_choice"].includes(slide.question_format)
          ? slide.choices.filter(Boolean)
          : [],
      fields: slide.slide_type === "participant_info" ? slide.fields : [],
    }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    const hasNewContent = newSlides.some(
      (s) => s.prompt.trim() || s.title.trim() || s.choices?.length
    );

    try {
      await api.patch(`/api/organizations/${slug}/meetings/${id}/`, {
        title: title.trim(),
        description: description.trim(),
        scheduled_start_at: scheduledStartAt
          ? new Date(scheduledStartAt).toISOString()
          : null,
        allow_start_early: allowStartEarly,
        is_anonymous: isAnonymous,
        ai_mode: aiMode,
      });

      if (hasNewContent) {
        const payloads = buildNewSlidePayloads().filter(
          (s) =>
            s.prompt ||
            s.title ||
            (s.slide_type === "standard" && s.question_format !== "text" && s.choices.length)
        );
        if (payloads.length) {
          const res = await api.post(
            `/api/organizations/${slug}/meetings/${id}/slides/add/`,
            { slides: payloads }
          );
          setMeeting(res.data.meeting || meeting);
        }
      }

      setSuccess("Meeting updated.");
      setNewSlides([emptyStandardSlide()]);
      const refreshed = await api.get(`/api/organizations/${slug}/meetings/${id}/`);
      setMeeting(refreshed.data);
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

          <div className="dashboard-card">
            <h2>Current slides ({meeting.slides?.length || 0})</h2>
            {meeting.slides?.length ? (
              <ul className="dashboard-list">
                {meeting.slides.map((slide) => (
                  <li key={slide.id} className="dashboard-list-item">
                    <span>{slideLabel(slide)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dashboard-empty">No slides yet.</p>
            )}
          </div>

          {!isLive && (
            <div className="dashboard-section">
              <div className="dashboard-section-header">
                <h2>Add slides</h2>
                <div className="dashboard-section-actions">
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addNewSlide("standard")}
                  >
                    + Standard
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addNewSlide("issue_card")}
                  >
                    + Issue card
                  </button>
                  <button
                    type="button"
                    className="dashboard-btn"
                    onClick={() => addNewSlide("political_issue_card")}
                  >
                    + Political issue
                  </button>
                </div>
              </div>

              {newSlides.map((slide, index) => (
                <div key={index} className="dashboard-card">
                  <div className="dashboard-card-header">
                    <strong>New slide {index + 1}</strong>
                    {newSlides.length > 1 && (
                      <button type="button" onClick={() => removeNewSlide(index)}>
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="dashboard-field">
                    <label>Type</label>
                    <select
                      value={slide.slide_type}
                      onChange={(e) => updateNewSlide(index, "slide_type", e.target.value)}
                    >
                      <option value="standard">Standard question</option>
                      <option value="issue_card">Issue card</option>
                      <option value="political_issue_card">Political issue card</option>
                    </select>
                  </div>

                  <div className="dashboard-field">
                    <label>Prompt</label>
                    <textarea
                      value={slide.prompt}
                      onChange={(e) => updateNewSlide(index, "prompt", e.target.value)}
                    />
                  </div>

                  {slide.slide_type === "standard" && (
                    <>
                      <div className="dashboard-field">
                        <label>Format</label>
                        <select
                          value={slide.question_format}
                          onChange={(e) =>
                            updateNewSlide(index, "question_format", e.target.value)
                          }
                        >
                          <option value="text">Free text</option>
                          <option value="single_choice">Single choice</option>
                          <option value="multi_choice">Multiple choice</option>
                        </select>
                      </div>
                      {["single_choice", "multi_choice"].includes(slide.question_format) && (
                        <div className="dashboard-field">
                          <label>Choices (comma-separated)</label>
                          <input
                            value={slide.choices.join(", ")}
                            onChange={(e) =>
                              updateNewSlide(
                                index,
                                "choices",
                                e.target.value
                                  .split(",")
                                  .map((s) => s.trim())
                                  .filter(Boolean)
                              )
                            }
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
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
