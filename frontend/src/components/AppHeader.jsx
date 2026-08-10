import SiteNavLinks from "./SiteNavLinks";
import HeaderAccountLinks from "./HeaderAccountLinks";
import "../styles/Landing.css";

/**
 * App chrome for signed-in pages: full marketing nav + account actions.
 */
function AppHeader() {
  return (
    <header className="landing-nav landing-nav--with-account app-header">
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
