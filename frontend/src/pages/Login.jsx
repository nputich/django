import CodeLookup from "../components/CodeLookup";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

function Login() {
  return (
    <MarketingLayout mainClassName="landing-main landing-main--home">
      <section className="landing-hero landing-hero--home">
        <SiteLogo />
      </section>
      <section className="landing-code-section" aria-labelledby="landing-code-heading">
        <h1 id="landing-code-heading" className="landing-code-heading">
          Enter your <span className="landing-code-heading-accent">community code</span>
        </h1>
        <p className="landing-code-lead">
          Search by organization or meeting code to join a session.
        </p>
        <CodeLookup className="landing-code-lookup--home" />
      </section>
    </MarketingLayout>
  );
}

export default Login;
