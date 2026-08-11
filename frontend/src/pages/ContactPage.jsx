import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../api";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/EnterCode.css";
import "../styles/Contact.css";

const MESSAGE_MAX = 2000;

export default function ContactPage() {
  const [searchParams] = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState(() => searchParams.get("subject") || "");
  const [message, setMessage] = useState(() =>
    (searchParams.get("message") || "").slice(0, MESSAGE_MAX)
  );
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    try {
      const res = await api.post("/api/contact/", {
        name: name.trim(),
        email: email.trim(),
        subject: subject.trim(),
        message: message.trim(),
      });
      setSuccess(res.data.detail || "Thank you — your message has been sent.");
      setName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      const data = err.response?.data;
      if (typeof data === "object" && data !== null) {
        const firstKey = Object.keys(data)[0];
        const val = data[firstKey];
        setError(Array.isArray(val) ? val[0] : data.detail || "Could not send message.");
      } else {
        setError("Could not send message. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <MarketingLayout mainClassName="landing-main enter-code-page">
      <SiteLogo />
      <h1 className="enter-code-title">Contact Us</h1>
      <p className="enter-code-subtitle">
        Send us a message and we will get back to you as soon as we can.
      </p>

      {success && <p className="contact-success">{success}</p>}

      <form className="contact-form" onSubmit={handleSubmit}>
        <div className="contact-field">
          <label htmlFor="contact-name">Name</label>
          <input
            id="contact-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
            autoComplete="name"
          />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-email">Email</label>
          <input
            id="contact-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            maxLength={254}
            autoComplete="email"
          />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-subject">Subject</label>
          <input
            id="contact-subject"
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
            maxLength={200}
          />
        </div>

        <div className="contact-field">
          <label htmlFor="contact-message">Message</label>
          <textarea
            id="contact-message"
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, MESSAGE_MAX))}
            required
            maxLength={MESSAGE_MAX}
            rows={6}
          />
          <span className="contact-char-count">
            {message.length} / {MESSAGE_MAX}
          </span>
        </div>

        {error && <p className="contact-error">{error}</p>}

        <button type="submit" className="contact-submit" disabled={submitting}>
          {submitting ? "Sending..." : "Send message"}
        </button>
      </form>

      <p className="enter-code-alt">
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}
