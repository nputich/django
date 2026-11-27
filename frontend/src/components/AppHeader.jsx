import SiteNavLinks from "./SiteNavLinks";
import HeaderAccountLinks from "./HeaderAccountLinks";
import { isDevEnvironment } from "../envFlags";
import "../styles/Landing.css";

/**
 * App chrome for signed-in pages: full marketing nav + account actions.
 */
function AppHeader() {
  const isDev = isDevEnvironment();

  return (
    <header
      className={[
        "landing-nav",
        "landing-nav--with-account",
        "app-header",
        isDev ? "landing-nav--dev" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {isDev && (
        <div className="landing-dev-banner" role="status">
          Development environment — not production
        </div>
      )}
      <div className="landing-nav-inner">
        <SiteNavLinks />
      </div>
      <div className="landing-nav-login landing-nav-login--account">
        <HeaderAccountLinks />
      </div>
    </header>
  );
}

export default AppHeader;
