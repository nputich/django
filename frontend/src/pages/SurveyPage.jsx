import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

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

  const handleChange = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const payload = {
      response_session: getResponseSession(),
      answers: Object.entries(answers).map(([question_id, value]) => ({
        question_id: Number(question_id),
        value,
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

  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>{survey.title}</h1>
      {survey.description && <p>{survey.description}</p>}
      <p className="resource-meta">{survey.organization_name}</p>

      <form onSubmit={handleSubmit} className="resource-form">
        {survey.questions.map((q) => (
          <label key={q.id} className="resource-field">
            <span>{q.text}</span>
            <textarea
              required
              value={answers[q.id] || ""}
              onChange={(e) => handleChange(q.id, e.target.value)}
            />
          </label>
        ))}
        {error && <p className="landing-code-error">{error}</p>}
        <button type="submit" className="landing-code-button">
          Submit
        </button>
      </form>
    </div>
  );
}