import SiteNavLinks from "./SiteNavLinks";
import SiteFooter from "./SiteFooter";
import HeaderLoginAccordion from "./HeaderLoginAccordion";
import HeaderAccountLinks from "./HeaderAccountLinks";
import { isAccessTokenValid } from "../auth";
import "../styles/Landing.css";

export default function MarketingLayout({
  children,
  showLogin = true,
  showFooter = true,
  mainClassName = "landing-main",
}) {
  const loggedIn = isAccessTokenValid();
  const showLoginPanel = showLogin && !loggedIn;
  const showAccountPanel = loggedIn;

  return (
    <div className="landing">
      <header
        className={[
          "landing-nav",
          showLoginPanel ? "landing-nav--with-login" : "",
          showAccountPanel ? "landing-nav--with-account" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div className="landing-nav-inner">
          <SiteNavLinks />
        </div>
        {showLoginPanel && (
          <div className="landing-nav-login">
            <HeaderLoginAccordion />
          </div>
        )}
        {showAccountPanel && (
          <div className="landing-nav-login landing-nav-login--account">
            <HeaderAccountLinks />
          </div>
        )}
      </header>
      <main className={mainClassName}>{children}</main>
      {showFooter && <SiteFooter />}
    </div>
  );
}
