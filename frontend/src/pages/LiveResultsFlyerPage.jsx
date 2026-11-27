import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { liveResultsUrl, qrCodeImageUrl, resourceJoinUrl } from "../meetingFlyer";
import "../styles/MeetingFlyer.css";
import "../styles/LiveResults.css";

export default function LiveResultsFlyerPage({ kind = "meeting" }) {
  const { id } = useParams();
  const isSurvey = kind === "survey";
  const [resource, setResource] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/${isSurvey ? "surveys" : "meetings"}/${id}/`)
      .then((res) => {
        if (!cancelled) setResource(res.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail || "Could not load this page.");
      });
    return () => {
      cancelled = true;
    };
  }, [id, isSurvey]);

  const resultsUrl = useMemo(() => liveResultsUrl(kind, id), [kind, id]);
  const joinUrl = useMemo(() => resourceJoinUrl(kind, id), [kind, id]);
  const resultsQr = useMemo(() => qrCodeImageUrl(resultsUrl, 420), [resultsUrl]);
  const joinQr = useMemo(() => qrCodeImageUrl(joinUrl, 240), [joinUrl]);

  const handleDownloadQr = async () => {
    try {
      const res = await fetch(resultsQr);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${kind}-${id}-live-results-qr.png`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      window.open(resultsQr, "_blank", "noopener,noreferrer");
    }
  };

  if (error) {
    return (
      <div className="meeting-flyer-page meeting-flyer-page--error">
        <p>{error}</p>
        <Link to="/">← Home</Link>
      </div>
    );
  }

  if (!resource) {
    return (
      <div className="meeting-flyer-page">
        <p className="meeting-flyer-loading">Loading…</p>
      </div>
    );
  }

  const enabled = isSurvey
    ? resource.live_results_for_respondents
    : resource.live_results_for_participants;
  const noun = isSurvey ? "survey" : "meeting";

  return (
    <div className="meeting-flyer-page">
      <div className="meeting-flyer-toolbar no-print">
        <button type="button" className="meeting-flyer-toolbar-btn" onClick={() => window.print()}>
          Print
        </button>
        <button
          type="button"
          className="meeting-flyer-toolbar-btn meeting-flyer-toolbar-btn--secondary"
          onClick={handleDownloadQr}
        >
          Download results QR image
        </button>
        {!enabled && (
          <span className="landing-code-error">
            Live results are off for this {noun}. Turn them on before sharing this sheet.
          </span>
        )}
      </div>

      <article className="meeting-flyer-sheet">
        {resource.organization_name && (
          <p className="meeting-flyer-org">{resource.organization_name}</p>
        )}
        <h1 className="meeting-flyer-title">{resource.title}</h1>
        <p className="meeting-flyer-desc">See the combined results live as they are shared.</p>

        <div className="meeting-flyer-hero">
          <div className="meeting-flyer-qr">
            <img src={resultsQr} width={420} height={420} alt="" />
            <p className="meeting-flyer-scan">Scan to see live results</p>
          </div>
          <div className="meeting-flyer-join">
            <p className="meeting-flyer-link">
              Direct link: <span>{resultsUrl.replace(/^https?:\/\//, "")}</span>
            </p>
          </div>
        </div>

        <div className="live-results-flyer-secondary">
          <img src={joinQr} width={240} height={240} alt="" />
          <div>
            <p>
              <strong>Haven&apos;t taken part yet?</strong> Scan this code to{" "}
              {isSurvey ? "take the survey" : "join the meeting"} first.
            </p>
            <p className="meeting-flyer-link">{joinUrl.replace(/^https?:\/\//, "")}</p>
          </div>
        </div>

        <h2 className="meeting-flyer-steps-title">How it works</h2>
        <ol className="meeting-flyer-steps">
          <li>Scan the large QR code with your phone camera.</li>
          {isSurvey ? (
            <li>Submit the survey if you have not already. Results are for people who took part.</li>
          ) : (
            <li>Join the meeting if asked. No account is needed for anonymous meetings.</li>
          )}
          <li>
            Results appear one question at a time when the {isSurvey ? "organizer" : "facilitator"}{" "}
            shares them.
          </li>
          <li>
            Tap <strong>Refresh results</strong> to see the latest numbers.
          </li>
        </ol>

        <p className="meeting-flyer-foot">
          Only combined totals are shown. Individual answers are never displayed.
        </p>
      </article>
    </div>
  );
}
