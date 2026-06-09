import { Link } from "react-router-dom";
import Form from "../components/Form";
import CodeLookup from "../components/CodeLookup";
import SiteNavLinks from "../components/SiteNavLinks";
import SiteFooter from "../components/SiteFooter";
import logo from "../assets/logo-full.png";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

function Login() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Link to="/" className="landing-nav-brand">
          <img src={logo} alt="" className="landing-nav-logo" aria-hidden />
          <span className="landing-nav-name">
            communi<span>B</span>
          </span>
        </Link>
        <div className="landing-nav-right">
          <div className="landing-nav-toolbar">
            <SiteNavLinks />
            <Form route="/api/token/" method="login" compact hideFooter />
          </div>
          <p className="landing-nav-register">
            New here? <Link to="/register">Register</Link>
          </p>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="landing-logo-wrap">
            <img src={logo} alt="communiB" className="landing-logo" />
          </div>
          <div className="landing-tagline">
            <strong>Better communities start here.</strong>
            <p>
              Connect with your organization, participate in surveys, share
              feedback, and help shape decisions that matter.
            </p>
          </div>
        </section>

        <CodeLookup />
      </main>

      <SiteFooter />
    </div>
  );
}

export default Login;
