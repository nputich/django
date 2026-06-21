import SiteNavLinks from "./SiteNavLinks";
import SiteFooter from "./SiteFooter";
import Form from "./Form";
import "../styles/Landing.css";

export default function MarketingLayout({
  children,
  showLogin = true,
  showFooter = true,
  mainClassName = "landing-main",
}) {
  return (
    <div className="landing">
      <header className="landing-nav landing-nav--end">
        <div className="landing-nav-right">
          <div className="landing-nav-toolbar">
            <SiteNavLinks />
            {showLogin && (
              <Form route="/api/token/" method="login" compact hideFooter />
            )}
          </div>
        </div>
      </header>
      <main className={mainClassName}>{children}</main>
      {showFooter && <SiteFooter />}
    </div>
  );
}
