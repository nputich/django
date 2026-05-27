import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import Form from "../components/Form";
import CodeLookup from "../components/CodeLookup";
import { ACCESS_TOKEN } from "../constants";
import logo from "../assets/logo-full.png";
import "../styles/Landing.css";

const YOUTUBE = "https://www.youtube.com/@communib";
const DONATE = "https://www.paypal.com/ncp/payment/YQWJCEH54LKU8";

function Login() {
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem(ACCESS_TOKEN)) {
      navigate("/app", { replace: true });
    }
  }, [navigate]);

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
          <nav className="landing-nav-links" aria-label="Main navigation">
            <Link className="landing-nav-pill" to="/org">
              Organizations
            </Link>
            <a
              className="landing-nav-pill"
              href={YOUTUBE}
              target="_blank"
              rel="noopener noreferrer"
            >
              YouTube
            </a>
            <a
              className="landing-nav-pill landing-nav-pill--primary"
              href={DONATE}
              target="_blank"
              rel="noopener noreferrer"
            >
              Donate
            </a>
          </nav>
          <Form route="/api/token/" method="login" compact />
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="landing-logo-wrap">
            <img src={logo} alt="communiB" className="landing-logo" />
          </div>
          <p className="landing-tagline">
            <strong>Better communities start here.</strong>
          </p>
        </section>

        <CodeLookup />
      </main>

      <footer className="landing-footer">
        <p>© {new Date().getFullYear()} communiB</p>
      </footer>
    </div>
  );
}

export default Login;
