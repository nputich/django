import Logo from "./Logo";
import SiteFooter from "./SiteFooter";
import "../../styles/AuthLayout.css";

function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <div className="auth-layout-top">
        <Logo />
      </div>
      <div className="auth-layout-main">{children}</div>
      <SiteFooter />
    </div>
  );
}

export default AuthLayout;
