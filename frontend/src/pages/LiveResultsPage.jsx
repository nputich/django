import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { ensureValidSession } from "../auth";
import LiveResultsPanel from "../components/LiveResultsPanel";
import {
  clearMeetingParticipant,
  getMeetingParticipant,
  saveMeetingParticipant,
} from "../meetingParticipant";
import { getSurveyResponseSession } from "../surveySession";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/LiveResults.css";

function MeetingLiveResults({ id }) {
  const [meeting, setMeeting] = useState(null);
  const [session, setSession] = useState(null);
  const [participant, setParticipant] = useState(() => getMeetingParticipant(id));
  const [privateCode, setPrivateCode] = useState("");
  const [error, setError] = useState("");
  const [joinError, setJoinError] = useState("");
  const [joining, setJoining] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.get(`/api/meetings/${id}/`),
      api.get(`/api/meetings/${id}/session/`).catch(() => ({ data: null })),
    ])
      .then(([meetingRes, sessionRes]) => {
        if (cancelled) return;
        setMeeting(meetingRes.data);
        setSession(sessionRes.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || "Could not load meeting.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    if (session?.id && participant?.session_id && participant.session_id !== session.id) {
      clearMeetingParticipant(id);
      setParticipant(null);
    }
  }, [id, session?.id, participant?.session_id]);

  const handleJoin = async () => {
    setJoinError("");
    setJoining(true);
    try {
      const res = await api.post(`/api/meetings/${id}/join/`, { private_code: privateCode });
      const record = {
        attendance_id: res.data.attendance_id,
        participant_id: res.data.participant_id,
        is_anonymous: res.data.is_anonymous,
        session_id: res.data.session?.id,
      };
      saveMeetingParticipant(id, record);
      setParticipant(record);
    } catch (err) {
      setJoinError(err.response?.data?.detail || "Could not join meeting.");
    } finally {
      setJoining(false);
    }
  };

  if (loading) return <p>Loading…</p>;
  if (error || !meeting) return <p className="landing-code-error">{error || "Meeting not found."}</p>;

  const status = session?.status;
  const sessionOpen = status === "live" || status === "paused";
  const needsLogin =
    ["semi_public", "private"].includes(meeting.access_mode) && !ensureValidSession();

  let body;
  if (!meeting.live_results_for_participants) {
    body = <p className="resource-note">Live results are not turned on for this meeting.</p>;
  } else if (participant?.attendance_id && status && status !== "scheduled") {
    body = <LiveResultsPanel kind="meeting" resourceId={id} identity={participant.attendance_id} />;
  } else if (!sessionOpen) {
    body = (
      <p className="resource-note">
        {status === "ended"
          ? "This meeting has ended."
          : "This meeting has not started yet. Check back once the facilitator starts it."}
      </p>
    );
  } else if (needsLogin) {
    body = (
      <div className="meeting-gate">
        <p>Log in to join this meeting and see its results.</p>
        <Link to="/" className="landing-code-button meeting-gate-link">
          Go to login
        </Link>
      </div>
    );
  } else {
    body = (
      <div className="meeting-join">
        <p>Join the meeting to see the results the facilitator shares.</p>
        {meeting.access_mode === "private" && (
          <label className="resource-field">
            <span>Private meeting code</span>
            <input
              type="text"
              value={privateCode}
              onChange={(e) => setPrivateCode(e.target.value.toUpperCase())}
            />
          </label>
        )}
        {joinError && <p className="landing-code-error">{joinError}</p>}
        <button type="button" className="landing-code-button" disabled={joining} onClick={handleJoin}>
          {joining ? "Joining…" : "Join to see results"}
        </button>
      </div>
    );
  }

  return (
    <>
      <h1>{meeting.title}</h1>
      {meeting.organization_name && <p className="resource-meta">{meeting.organization_name}</p>}
      {body}
      <div className="live-results-page-actions">
        <Link to={`/m/${id}`}>Answer the meeting questions</Link>
      </div>
    </>
  );
}

function SurveyLiveResults({ id }) {
  const [survey, setSurvey] = useState(null);
  const [error, setError] = useState("");
  const [identity] = useState(() => getSurveyResponseSession());

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/surveys/${id}/`)
      .then((res) => {
        if (!cancelled) setSurvey(res.data);
      })
      .catch(() => {
        if (!cancelled) setError("Survey not found or no longer open.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="landing-code-error">{error}</p>;
  if (!survey) return <p>Loading…</p>;

  return (
    <>
      <h1>{survey.title}</h1>
      {survey.organization_name && <p className="resource-meta">{survey.organization_name}</p>}
      {survey.live_results_for_respondents ? (
        <LiveResultsPanel kind="survey" resourceId={id} identity={identity} />
      ) : (
        <p className="resource-note">Live results are not turned on for this survey.</p>
      )}
      <div className="live-results-page-actions">
        <Link to={`/s/${id}`}>Take the survey</Link>
      </div>
    </>
  );
}

export default function LiveResultsPage({ kind = "meeting" }) {
  const { id } = useParams();
  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      {kind === "survey" ? <SurveyLiveResults id={id} /> : <MeetingLiveResults id={id} />}
    </div>
  );
}
