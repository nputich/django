import { Link } from "react-router-dom";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

function NotFound() {
  return (
    <MarketingLayout mainClassName="landing-main enter-code-page">
      <SiteLogo variant="compact" />
      <h1 className="enter-code-title">Page not found</h1>
      <p className="enter-code-subtitle">
        The page you are looking for does not exist or has moved.
      </p>
      <p className="enter-code-alt">
        <Link to="/">← Back to home</Link>
        {" · "}
        <Link to="/enter-code">Enter a code</Link>
      </p>
    </MarketingLayout>
  );
}

export default NotFound;
