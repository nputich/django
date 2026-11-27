import { useState } from "react";
import { useLocation } from "react-router-dom";
import Form from "./Form";

function ChevronDown({ className = "" }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export default function HeaderLoginAccordion() {
  const location = useLocation();
  const [open, setOpen] = useState(Boolean(location.state?.from));

  return (
    <div
      className={`landing-login-accordion${
        open ? " landing-login-accordion--open" : ""
      }`}
    >
      <button
        type="button"
        className="landing-login-accordion-trigger"
        aria-expanded={open}
        aria-controls="header-login-panel"
        onClick={() => setOpen((value) => !value)}
      >
        <span>Log In</span>
        <ChevronDown className="landing-login-accordion-chevron" />
      </button>
      <div id="header-login-panel" className="landing-login-accordion-panel">
        <Form route="/api/token/" method="login" header />
      </div>
    </div>
  );
}
