import { Link } from "react-router-dom";
import Form from "../components/Form";
import CodeLookup from "../components/CodeLookup";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

function Login() {
  return (
    <MarketingLayout>
      <section className="landing-hero">
        <SiteLogo variant="hero" />
        <div className="landing-tagline">
          <strong>Better communities start here.</strong>
          <p>
            Connect with your organization, participate in surveys, share
            feedback, and help shape decisions that matter.
          </p>
        </div>
      </section>
      <CodeLookup />
      <p className="landing-nav-register landing-hero-register">
        New here? <Link to="/register">Register</Link>
      </p>
    </MarketingLayout>
  );
}

export default Login;
