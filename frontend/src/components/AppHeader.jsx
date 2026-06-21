import { Link } from "react-router-dom";
import "../styles/Landing.css";

function AppHeader() {
  return (
    <header className="landing-nav landing-nav--end app-header">
      <nav className="landing-nav-links" aria-label="Account">
        <Link className="landing-nav-pill" to="/">
          Home
        </Link>
        <Link className="landing-nav-pill" to="/dashboard">
          Dashboard
        </Link>
        <Link className="landing-nav-pill landing-nav-pill--logout" to="/logout">
          Log out
        </Link>
      </nav>
    </header>
  );
}

export default AppHeader;
