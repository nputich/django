import { Link } from "react-router-dom";
import logo from "../assets/logo-full.png";
import CodeLookup from "../components/CodeLookup";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

export default function EnterCode() {
  return (
    <div className="enter-code">
      <Link to="/" className="enter-code-back">
        ← Back to home
      </Link>
      <div className="enter-code-logo-wrap">
        <img src={logo} alt="communiB" className="enter-code-logo" />
      </div>
      <h1>Enter a code</h1>
      <p className="enter-code-subtitle">
        Enter your community or organization code below.
      </p>
      <CodeLookup className="landing-code-lookup--standalone" />
    </div>
  );
}
