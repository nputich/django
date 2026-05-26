import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import Form from "../components/Form";
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
      <header className="landing-hero">
        <img src={logo} alt="communiB" className="landing-logo" />
        <p className="landing-tagline">Better communities start here.</p>
      </header>

      <nav className="landing-grid" aria-label="Main navigation">
        <Link className="landing-card" to="/enter-code">
          <h2>Enter a code</h2>
          <p>Look up a community or organization</p>
        </Link>

        <Link className="landing-card" to="/org">
          <h2>Organization accounts</h2>
          <p>For organizations — coming soon</p>
        </Link>

        <a
          className="landing-card"
          href={YOUTUBE}
          target="_blank"
          rel="noopener noreferrer"
        >
          <h2>YouTube</h2>
          <p>Videos and updates</p>
        </a>

        <a
          className="landing-card landing-card--donate"
          href={DONATE}
          target="_blank"
          rel="noopener noreferrer"
        >
          <h2>Donate</h2>
          <p>Support communiB via PayPal</p>
        </a>
      </nav>

      <section className="landing-login">
        <Form route="/api/token/" method="login" />
      </section>

      <footer className="landing-footer">
        <p>© {new Date().getFullYear()} communiB</p>
      </footer>
    </div>
  );
}

export default Login;
