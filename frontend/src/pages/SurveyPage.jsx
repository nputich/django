import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import ContentBlock from "../components/ContentBlock";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/Tags.css";

function getResponseSession() {
  let session = localStorage.getItem("survey_response_session");
  if (!session) {
    session = crypto.randomUUID();
    localStorage.setItem("survey_response_session", session);
  }
  return session;
}

export default function SurveyPage() {
  const { id } = useParams();
  const [survey, setSurvey] = useState(null);
  const [answers, setAnswers] = useState({});
  const [disclosureAccepted, setDisclosureAccepted] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get(`/api/surveys/${id}/`)
      .then((res) => setSurvey(res.data))
      .catch(() => setError("Survey not found."))
      .finally(() => setLoading(false));
  }, [id]);

  const mainQuestions = useMemo(
    () => (survey?.questions || []).filter((q) => !q.is_demographic),
    [survey]
  );
  const demographicQuestions = useMemo(
    () => (survey?.questions || []).filter((q) => q.is_demographic),
    [survey]
  );

  const handleChange = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const answerable = (survey.questions || []).filter((q) => q.question_type !== "content");
    const payload = {
      response_session: getResponseSession(),
      answers: answerable
        .filter((q) => answers[q.id] != null && String(answers[q.id]).trim() !== "")
        .map((q) => ({
          question_id: q.id,
          value: Array.isArray(answers[q.id]) ? answers[q.id].join(", ") : String(answers[q.id]),
        })),
    };

    try {
      await api.post(`/api/surveys/${id}/submit/`, payload);
      setSubmitted(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not submit survey.");
    }
  };

  if (loading) return <div className="resource-page">Loading...</div>;
  if (error && !survey) {
    return (
      <div className="resource-page">
        <p>{error}</p>
        <Link to="/">Back to home</Link>
      </div>
    );
  }
  if (submitted) {
    return (
      <div className="resource-page">
        <h1>Thank you</h1>
        <p>Your responses have been submitted.</p>
        <Link to="/">Back to home</Link>
      </div>
    );
  }

  if (!disclosureAccepted) {
    return (
      <div className="resource-page">
        <Link to="/" className="resource-back">
          &larr; Back to home
        </Link>
        <h1>{survey.title}</h1>
        {survey.description && <p>{survey.description}</p>}
        <p className="resource-meta">{survey.organization_name}</p>
        <div className="meeting-disclosure" role="note">
          <p className="meeting-disclosure-anon">
            {survey.disclosure?.is_anonymous
              ? "This survey is anonymous"
              : "This survey is not anonymous"}
          </p>
          <p>{survey.disclosure?.text}</p>
        </div>
        <button
          type="button"
          className="landing-code-button"
          onClick={() => setDisclosureAccepted(true)}
        >
          Continue to survey
        </button>
      </div>
    );
  }

  const renderQuestion = (q) => {
    if (q.question_type === "content") {
      return (
        <div key={q.id} className="resource-field">
          <ContentBlock title={q.text} content={q.content || q.config} />
        </div>
      );
    }
    if (q.question_type === "choice") {
      return (
        <fieldset key={q.id} className="resource-field">
          <legend>{q.text}</legend>
          {(q.choices || []).map((opt) => (
            <label key={opt} className="meeting-check-option">
              <input
                type="radio"
                name={`q-${q.id}`}
                checked={answers[q.id] === opt}
                onChange={() => handleChange(q.id, opt)}
              />
              {opt}
            </label>
          ))}
        </fieldset>
      );
    }
    return (
      <label key={q.id} className="resource-field">
        <span>
          {q.text}
          {q.is_demographic ? "" : " *"}
        </span>
        <textarea
          required={!q.is_demographic}
          value={answers[q.id] || ""}
          onChange={(e) => handleChange(q.id, e.target.value)}
        />
      </label>
    );
  };

  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>{survey.title}</h1>
      <p className="resource-meta">{survey.organization_name}</p>

      <form onSubmit={handleSubmit} className="resource-form">
        {mainQuestions.map(renderQuestion)}

        {demographicQuestions.length > 0 && (
          <div className="dashboard-card" style={{ marginTop: "1rem" }}>
            <h2>About you (optional)</h2>
            <p className="dashboard-meta">
              These questions help the organizer understand who responded. You can skip any of
              them.
            </p>
            {demographicQuestions.map(renderQuestion)}
          </div>
        )}

        {error && <p className="landing-code-error">{error}</p>}
        <button type="submit" className="landing-code-button">
          Submit
        </button>
      </form>
    </div>
  );
}
