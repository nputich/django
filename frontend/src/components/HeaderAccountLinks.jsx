import { Link } from "react-router-dom";

/** Account actions for the top nav when the user is signed in. */
export default function HeaderAccountLinks() {
  return (
    <nav className="landing-nav-account" aria-label="Account">
      <Link className="landing-nav-pill" to="/dashboard">
        Dashboard
      </Link>
      <Link className="landing-nav-pill" to="/account">
        Account
      </Link>
      <Link className="landing-nav-pill landing-nav-pill--logout" to="/logout">
        Log out
      </Link>
    </nav>
  );
}
