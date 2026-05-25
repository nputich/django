import { Link, useLocation } from "react-router-dom";
import Logo from "./Logo";
import "../../styles/SiteHeader.css";

function SiteHeader() {
  const location = useLocation();
  const onApp = location.pathname.startsWith("/app");

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Logo />
        <nav className="site-nav" aria-label="Main">
          {onApp ? (
            <Link to="/" className="nav-link">
              Lookup
            </Link>
          ) : (
            <Link to="/login" className="nav-link">
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

export default SiteHeader;
