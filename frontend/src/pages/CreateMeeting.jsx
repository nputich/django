import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import { normalizeAccessCode } from "../accessCode";
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

function emptyParticipantInfoSlide(order) {
  return {
    order,
    slide_type: "participant_info",
    title: "About you",
    prompt: "",
    question_format: "",
    choices: [],
    fields: [
      {
        key: "zip_code",
        label: "Zip Code",
        required: false,
        field_type: "text",
        options: [],
      },
    ],
  };
}

export default function CreateMeeting() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [accessMode, setAccessMode] = useState("public");
  const [accessCode, setAccessCode] = useState("");
  const [scheduledStartAt, setScheduledStartAt] = useState("");
  const [allowStartEarly, setAllowStartEarly] = useState(false);
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [aiMode, setAiMode] = useState("none");
  const [includeInfoSlide, setIncludeInfoSlide] = useState(true);
  const [slides, setSlides] = useState([emptyStandardSlide(2)]);
  const [codeStatus, setCodeStatus] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);
  const [submitting, setSubmitting] = useState(false);

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

  const updateSlide = (index, field, value) => {
    setSlides((prev) =>
      prev.map((slide, i) => (i === index ? { ...slide, [field]: value } : slide))
    );
  };

  const addSlide = (slideType) => {
    setSlides((prev) => {
      const order = (includeInfoSlide ? 2 : 1) + prev.length;
      if (slideType === "issue_card") {
        return [
          ...prev,
          {
            order,
            slide_type: "issue_card",
            title: "",
            prompt: "Share a concern or suggestion.",
            question_format: "",
            choices: [],
            fields: [],
          },
        ];
      }
      if (slideType === "political_issue_card") {
        return [
          ...prev,
          {
            order,
            slide_type: "political_issue_card",
            title: "",
            prompt: "Describe a policy issue that matters to you.",
            question_format: "",
            choices: [],
            fields: [],
          },
        ];
      }
      return [...prev, emptyStandardSlide(order)];
    });
  };

  const removeSlide = (index) => {
    if (slides.length <= 1) return;
    setSlides((prev) => prev.filter((_, i) => i !== index));
  };

  const buildSlidesPayload = () => {
    const payload = [];
    let order = 1;
    if (includeInfoSlide) {
      payload.push({ ...emptyParticipantInfoSlide(1), order: 1 });
      order = 2;
    }
    slides.forEach((slide, index) => {
      payload.push({
        order: order + index,
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
      });
    });
    return payload;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess(null);
    setSubmitting(true);

    const payload = {
      title: title.trim(),
      description: description.trim(),
      access_mode: accessMode,
      access_code: accessCode.trim(),
      scheduled_start_at: scheduledStartAt
        ? new Date(scheduledStartAt).toISOString()
        : null,
      allow_start_early: allowStartEarly,
      is_anonymous: isAnonymous,
      ai_mode: aiMode,
      slides: buildSlidesPayload(),
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
            Schedule a structured meeting with slides. The community code lets participants
            find it via search or direct entry.
          </p>
        </div>

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
                checked={includeInfoSlide}
                onChange={(e) => setIncludeInfoSlide(e.target.checked)}
              />{" "}
              Include voluntary participant info slide
            </label>
          </div>

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
              Direct-entry community code for this meeting. Org and survey codes work the
              same way for their resources.
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
              <h2>Slides</h2>
              <div className="dashboard-section-actions">
                <button type="button" className="dashboard-btn" onClick={() => addSlide("standard")}>
                  + Standard
                </button>
                <button type="button" className="dashboard-btn" onClick={() => addSlide("issue_card")}>
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

            {slides.map((slide, index) => (
              <div key={index} className="dashboard-card">
                <div className="dashboard-card-header">
                  <strong>Slide {includeInfoSlide ? index + 2 : index + 1}</strong>
                  {slides.length > 1 && (
                    <button type="button" onClick={() => removeSlide(index)}>
                      Remove
                    </button>
                  )}
                </div>

                <div className="dashboard-field">
                  <label>Slide type</label>
                  <select
                    value={slide.slide_type}
                    onChange={(e) => updateSlide(index, "slide_type", e.target.value)}
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
                    onChange={(e) => updateSlide(index, "prompt", e.target.value)}
                    required={slide.slide_type === "standard"}
                  />
                </div>

                {slide.slide_type === "standard" && (
                  <>
                    <div className="dashboard-field">
                      <label>Format</label>
                      <select
                        value={slide.question_format}
                        onChange={(e) =>
                          updateSlide(index, "question_format", e.target.value)
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
                            updateSlide(
                              index,
                              "choices",
                              e.target.value
                                .split(",")
                                .map((s) => s.trim())
                                .filter(Boolean)
                            )
                          }
                          placeholder="Option A, Option B, Option C"
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>

          {error && <p className="dashboard-error">{error}</p>}

          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create meeting"}
          </button>
        </form>
      </main>
    </div>
  );
}
