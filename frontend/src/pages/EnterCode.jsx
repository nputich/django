import { Link } from "react-router-dom";
import CodeLookup from "../components/CodeLookup";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/CodeResults.css";
import "../styles/EnterCode.css";

export default function EnterCode() {
  return (
    <MarketingLayout mainClassName="landing-main landing-main--home">
      <section className="landing-hero">
        <SiteLogo />
      </section>
      <CodeLookup />
      <p className="enter-code-alt">
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}
