import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api";
import { meetingJoinUrl, qrCodeImageUrl } from "../meetingFlyer";
import "../styles/MeetingFlyer.css";

function formatWhen(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export default function MeetingFlyerPage() {
  const { id } = useParams();
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/api/meetings/${id}/`)
      .then((res) => {
        if (!cancelled) setMeeting(res.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || "Could not load meeting.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const joinUrl = useMemo(() => meetingJoinUrl(id), [id]);
  const qrUrl = useMemo(() => qrCodeImageUrl(joinUrl, 420), [joinUrl]);
  const siteHost = useMemo(() => {
    try {
      return new URL(joinUrl).host;
    } catch {
      return "communibetter.com";
    }
  }, [joinUrl]);

  const handlePrint = () => window.print();

  const handleDownloadQr = async () => {
    try {
      const res = await fetch(qrUrl);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `meeting-${id}-qr.png`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      window.open(qrUrl, "_blank", "noopener,noreferrer");
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

  if (!meeting) {
    return (
      <div className="meeting-flyer-page">
        <p className="meeting-flyer-loading">Loading flyer…</p>
      </div>
    );
  }

  const code = meeting.community_code || "";

  return (
    <div className="meeting-flyer-page">
      <div className="meeting-flyer-toolbar no-print">
        <button type="button" className="meeting-flyer-toolbar-btn" onClick={handlePrint}>
          Print flyer
        </button>
        <button
          type="button"
          className="meeting-flyer-toolbar-btn meeting-flyer-toolbar-btn--secondary"
          onClick={handleDownloadQr}
        >
          Download QR image
        </button>
        <Link to={`/m/${id}/details`} className="meeting-flyer-toolbar-link">
          Meeting details
        </Link>
      </div>

      <article className="meeting-flyer-sheet" id="meeting-flyer-sheet">
        {meeting.organization_name && (
          <p className="meeting-flyer-org">{meeting.organization_name}</p>
        )}
        <h1 className="meeting-flyer-title">{meeting.title}</h1>
        {meeting.description ? (
          <p className="meeting-flyer-desc">{meeting.description}</p>
        ) : null}

        <dl className="meeting-flyer-meta">
          {meeting.scheduled_start_at && (
            <>
              <dt>Starts</dt>
              <dd>{formatWhen(meeting.scheduled_start_at)}</dd>
            </>
          )}
          {meeting.scheduled_end_at && (
            <>
              <dt>Expected end</dt>
              <dd>{formatWhen(meeting.scheduled_end_at)}</dd>
            </>
          )}
          {meeting.location && (
            <>
              <dt>Location</dt>
              <dd>{meeting.location}</dd>
            </>
          )}
        </dl>

        <div className="meeting-flyer-hero">
          <div className="meeting-flyer-qr">
            <img src={qrUrl} width={420} height={420} alt="" />
            <p className="meeting-flyer-scan">Scan to participate</p>
          </div>
          <div className="meeting-flyer-join">
            <p>
              <strong>Or visit</strong> {siteHost}
            </p>
            {code ? (
              <>
                <p className="meeting-flyer-code-label">Enter community code:</p>
                <p className="meeting-flyer-code">{code}</p>
              </>
            ) : null}
            <p className="meeting-flyer-link">
              Direct link: <span>{joinUrl.replace(/^https?:\/\//, "")}</span>
            </p>
          </div>
        </div>

        <h2 className="meeting-flyer-steps-title">How to join on your phone</h2>
        <ol className="meeting-flyer-steps">
          <li>
            Open <strong>{siteHost}</strong> or scan the QR code.
          </li>
          {code ? (
            <li>
              On the home page, enter code <strong>{code}</strong> and select this
              meeting.
            </li>
          ) : (
            <li>Open the meeting link shown above.</li>
          )}
          <li>Follow the prompts to share your input.</li>
          {meeting.is_anonymous ? (
            <li>This meeting is anonymous — no account required.</li>
          ) : (
            <li>Sign in if prompted, then answer the questions.</li>
          )}
        </ol>

        <p className="meeting-flyer-foot">
          {meeting.is_anonymous
            ? "Responses are collected anonymously for this meeting."
            : "Thank you for participating."}
        </p>
      </article>
    </div>
  );
}
