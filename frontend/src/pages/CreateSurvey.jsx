import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

function emptyQuestion(order) {
  return { order, text: "", question_type: "text", choices: [] };
}

export default function CreateSurvey() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [codeStatus, setCodeStatus] = useState(null);
  const [isAnonymous, setIsAnonymous] = useState(true);
  const [questions, setQuestions] = useState([emptyQuestion(1)]);
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
        params: { code: code.trim(), type: "survey" },
      });
      setCodeStatus(res.data);
    } catch (err) {
      setCodeStatus({
        available: false,
        detail: err.response?.data?.detail || "Could not check code.",
      });
    }
  }, []);

  const updateQuestion = (index, field, value) => {
    setQuestions((prev) =>
      prev.map((q, i) => (i === index ? { ...q, [field]: value } : q))
    );
  };

  const addQuestion = () => {
    setQuestions((prev) => [...prev, emptyQuestion(prev.length + 1)]);
  };

  const removeQuestion = (index) => {
    if (questions.length <= 1) return;
    setQuestions((prev) =>
      prev.filter((_, i) => i !== index).map((q, i) => ({ ...q, order: i + 1 }))
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess(null);
    setSubmitting(true);

    const payload = {
      title: title.trim(),
      description: description.trim(),
      is_anonymous: isAnonymous,
      access_code: accessCode.trim(),
      questions: questions.map((q, i) => ({
        order: i + 1,
        text: q.text.trim(),
        question_type: q.question_type,
        choices: q.question_type === "choice" ? q.choices : [],
      })),
    };

    try {
      const res = await api.post(
        `/api/organizations/${slug}/surveys/`,
        payload
      );
      setSuccess(res.data);
      setTimeout(() => navigate(`/dashboard/${slug}`), 2500);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          JSON.stringify(err.response?.data) ||
          "Could not create survey."
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
          <h1>Create survey</h1>
          <p>Add questions and an access code for public search.</p>
        </div>

        {success && (
          <div className="dashboard-success">
            <strong>Survey created!</strong>
            <p>
              Access code: <span className="dashboard-code">{success.access_code.code}</span>
            </p>
            <p>Redirecting to dashboard...</p>
          </div>
        )}

        <form className="dashboard-form" onSubmit={handleSubmit}>
          <div className="dashboard-field">
            <label htmlFor="survey-title">Title</label>
            <input
              id="survey-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="survey-description">Description</label>
            <textarea
              id="survey-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="survey-code">Access code (optional)</label>
            <input
              id="survey-code"
              value={accessCode}
              onChange={(e) => {
                setAccessCode(e.target.value);
                setCodeStatus(null);
              }}
              onBlur={() => checkCode(accessCode)}
              placeholder="Leave blank to auto-generate"
            />
            <small>
              3–32 characters, letters, numbers, and hyphens. Must not be in
              use by an active survey.
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

          <div className="dashboard-field dashboard-field--inline">
            <input
              id="survey-anonymous"
              type="checkbox"
              checked={isAnonymous}
              onChange={(e) => setIsAnonymous(e.target.checked)}
            />
            <label htmlFor="survey-anonymous">Anonymous responses</label>
          </div>

          <div className="dashboard-card">
            <h2>Questions</h2>
            {questions.map((q, index) => (
              <div key={index} className="dashboard-question-block">
                <div className="dashboard-question-header">
                  <strong>Question {index + 1}</strong>
                  {questions.length > 1 && (
                    <button
                      type="button"
                      className="dashboard-link-btn"
                      onClick={() => removeQuestion(index)}
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div className="dashboard-field">
                  <label>Question text</label>
                  <textarea
                    value={q.text}
                    onChange={(e) => updateQuestion(index, "text", e.target.value)}
                    required
                  />
                </div>
                <div className="dashboard-field">
                  <label>Type</label>
                  <select
                    value={q.question_type}
                    onChange={(e) =>
                      updateQuestion(index, "question_type", e.target.value)
                    }
                  >
                    <option value="text">Text</option>
                    <option value="choice">Multiple choice</option>
                  </select>
                </div>
                {q.question_type === "choice" && (
                  <div className="dashboard-field">
                    <label>Choices (comma-separated)</label>
                    <input
                      value={(q.choices || []).join(", ")}
                      onChange={(e) =>
                        updateQuestion(
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
              </div>
            ))}
            <button type="button" className="dashboard-btn" onClick={addQuestion}>
              Add question
            </button>
          </div>

          {error && <p className="dashboard-error">{error}</p>}

          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create survey"}
          </button>
        </form>
      </main>
    </div>
  );
}
