import { Link, useLocation } from "react-router-dom";
import logo from "../assets/logo-full.png";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

const MESSAGES = {
  "/org": {
    title: "Organization accounts",
    body: "Organization sign-up and management are not available yet. Please check back later.",
    back: { to: "/", label: "← Back to home" },
  },
  "/search-another-way": {
    title: "Coming soon",
    body: "This feature is still under construction. Please check back later.",
    back: { to: "/enter-code", label: "← Back to Enter a code" },
  },
};

export default function UnderConstruction() {
  const { pathname } = useLocation();
  const content = MESSAGES[pathname] ?? MESSAGES["/search-another-way"];

  return (
    <div className="enter-code">
      <div className="enter-code-logo-wrap">
        <img src={logo} alt="communiB" className="enter-code-logo" />
      </div>
      <h1>{content.title}</h1>
      <p className="enter-code-subtitle">{content.body}</p>
      <p className="enter-code-alt">
        <Link to={content.back.to}>{content.back.label}</Link>
        {" · "}
        <Link to="/">Home</Link>
      </p>
    </div>
  );
}
