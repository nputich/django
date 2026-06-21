import SiteNavLinks from "./SiteNavLinks";
import SiteFooter from "./SiteFooter";
import Form from "./Form";
import { isAccessTokenValid } from "../auth";
import "../styles/Landing.css";

export default function MarketingLayout({
  children,
  showLogin = true,
  showFooter = true,
  mainClassName = "landing-main",
}) {
  const showLoginPanel = showLogin && !isAccessTokenValid();

  return (
    <div className="landing">
      <header
        className={`landing-nav${showLoginPanel ? " landing-nav--with-login" : ""}`}
      >
        <div className="landing-nav-inner">
          <SiteNavLinks />
        </div>
        {showLoginPanel && (
          <div className="landing-nav-login">
            <Form route="/api/token/" method="login" header />
          </div>
        )}
      </header>
      <main className={mainClassName}>{children}</main>
      {showFooter && <SiteFooter />}
    </div>
  );
}
