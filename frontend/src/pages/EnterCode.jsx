import { Link } from "react-router-dom";
import CodeLookup from "../components/CodeLookup";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/EnterCode.css";

export default function EnterCode() {
  return (
    <MarketingLayout mainClassName="landing-main enter-code-page">
      <SiteLogo variant="compact" />
      <h1 className="enter-code-title">Enter a code</h1>
      <p className="enter-code-subtitle">
        Enter your community or organization code below.
      </p>
      <CodeLookup className="landing-code-lookup--standalone" />
      <p className="enter-code-alt">
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}
