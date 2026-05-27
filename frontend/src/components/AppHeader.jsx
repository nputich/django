import { Link } from "react-router-dom";
import logo from "../assets/logo-full.png";
import "../styles/Landing.css";

function AppHeader() {
  return (
    <header className="landing-nav app-header">
      <Link to="/app" className="landing-nav-brand">
        <img src={logo} alt="" className="landing-nav-logo" aria-hidden />
        <span className="landing-nav-name">
          communi<span>B</span>
        </span>
      </Link>
      <nav className="landing-nav-links" aria-label="Account">
        <Link className="landing-nav-pill" to="/app">
          Home
        </Link>
        <Link className="landing-nav-pill landing-nav-pill--logout" to="/logout">
          Log out
        </Link>
      </nav>
    </header>
  );
}

export default AppHeader;
