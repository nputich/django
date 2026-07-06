import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";

function emptyQuestion() {
  return { text: "", question_type: "text", choices: [] };
}

export default function EditSurvey() {
  const { slug, id } = useParams();
  const navigate = useNavigate();
  const [survey, setSurvey] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [newQuestions, setNewQuestions] = useState([emptyQuestion()]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/api/organizations/${slug}/surveys/${id}/`);
        if (cancelled) return;
        const s = res.data;
        setSurvey(s);
        setTitle(s.title || "");
        setDescription(s.description || "");
        setIsAnonymous(!!s.is_anonymous);
        setIsActive(!!s.is_active);
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not load survey.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, id]);

  const updateNewQuestion = (index, field, value) => {
    setNewQuestions((prev) =>
      prev.map((q, i) => (i === index ? { ...q, [field]: value } : q))
    );
  };

  const addNewQuestion = () => {
    setNewQuestions((prev) => [...prev, emptyQuestion()]);
  };

  const removeNewQuestion = (index) => {
    if (newQuestions.length <= 1) return;
    setNewQuestions((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    const questionsToAdd = newQuestions
      .map((q) => ({
        text: q.text.trim(),
        question_type: q.question_type,
        choices: q.question_type === "choice" ? q.choices : [],
      }))
      .filter((q) => q.text);

    try {
      await api.patch(`/api/organizations/${slug}/surveys/${id}/`, {
        title: title.trim(),
        description: description.trim(),
        is_anonymous: isAnonymous,
        is_active: isActive,
      });

      if (questionsToAdd.length) {
        const res = await api.post(
          `/api/organizations/${slug}/surveys/${id}/questions/`,
          { questions: questionsToAdd }
        );
        setSurvey(res.data.survey);
      } else {
        const refreshed = await api.get(`/api/organizations/${slug}/surveys/${id}/`);
        setSurvey(refreshed.data);
      }

      setSuccess("Survey updated.");
      setNewQuestions([emptyQuestion()]);
      setTimeout(() => navigate(`/dashboard/${slug}`), 2000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          JSON.stringify(err.response?.data) ||
          "Could not update survey."
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
          <p>Loading survey...</p>
        </main>
      </div>
    );
  }

  if (!survey) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p className="dashboard-error">{error || "Survey not found."}</p>
          <Link to={`/dashboard/${slug}`} className="dashboard-back">
            ← Back to dashboard
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to dashboard
        </Link>

        <div className="dashboard-header">
          <h1>Edit survey</h1>
          <p>
            {survey.title} · {survey.is_active ? "Active" : "Inactive"}
            {(survey.access_codes ?? []).map((code) => (
              <span key={code.id} className="dashboard-code" style={{ marginLeft: "0.5rem" }}>
                {code.code}
              </span>
            ))}
          </p>
        </div>

        {success && <div className="dashboard-success">{success}</div>}

        <form className="dashboard-form" onSubmit={handleSubmit}>
          <div className="dashboard-field">
            <label htmlFor="edit-survey-title">Title</label>
            <input
              id="edit-survey-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="dashboard-field">
            <label htmlFor="edit-survey-description">Description</label>
            <textarea
              id="edit-survey-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="dashboard-field dashboard-field--row">
            <label>
              <input
                type="checkbox"
                checked={isAnonymous}
                onChange={(e) => setIsAnonymous(e.target.checked)}
              />{" "}
              Anonymous responses
            </label>
          </div>

          <div className="dashboard-field dashboard-field--row">
            <label>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />{" "}
              Survey active (accepting responses)
            </label>
          </div>

          <div className="dashboard-card">
            <h2>Current questions ({survey.questions?.length || 0})</h2>
            {survey.questions?.length ? (
              <ol className="dashboard-list">
                {survey.questions.map((q) => (
                  <li key={q.id} className="dashboard-list-item">
                    <div>
                      <strong>#{q.order}</strong> {q.text}
                      <p className="dashboard-meta">{q.question_type}</p>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="dashboard-empty">No questions yet.</p>
            )}
          </div>

          <div className="dashboard-card">
            <h2>Add questions</h2>
            {newQuestions.map((q, index) => (
              <div key={index} className="dashboard-question-block">
                <div className="dashboard-question-header">
                  <strong>New question {index + 1}</strong>
                  {newQuestions.length > 1 && (
                    <button
                      type="button"
                      className="dashboard-link-btn"
                      onClick={() => removeNewQuestion(index)}
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div className="dashboard-field">
                  <label>Question text</label>
                  <textarea
                    value={q.text}
                    onChange={(e) => updateNewQuestion(index, "text", e.target.value)}
                  />
                </div>
                <div className="dashboard-field">
                  <label>Type</label>
                  <select
                    value={q.question_type}
                    onChange={(e) =>
                      updateNewQuestion(index, "question_type", e.target.value)
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
                        updateNewQuestion(
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
            <button type="button" className="dashboard-btn" onClick={addNewQuestion}>
              Add another question
            </button>
          </div>

          {error && <p className="dashboard-error">{error}</p>}

          <button
            type="submit"
            className="dashboard-btn dashboard-btn--primary"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Save changes"}
          </button>
        </form>
      </main>
    </div>
  );
}
