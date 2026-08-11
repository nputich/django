import { Link } from "react-router-dom";
import { CREATE_ORGANIZATION_PATH } from "../constants/orgCreation";
import "../styles/CreateOrganization.css";

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
      <div className="landing-nav-account-secondary">
        <Link to="/dashboard/inbox">Messages</Link>
        <Link to="/dashboard">My Organizations</Link>
        <Link to={CREATE_ORGANIZATION_PATH}>Create an Organization</Link>
      </div>
    </nav>
  );
}
