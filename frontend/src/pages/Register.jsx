import { Link, useLocation } from "react-router-dom";
import Form from "../components/Form";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

function Register() {
  const location = useLocation();
  const returnState = location.state?.from ? { from: location.state.from } : undefined;

  return (
    <MarketingLayout
      showLogin={false}
      mainClassName="landing-main landing-main--centered"
    >
      <SiteLogo />
      <div className="landing-login-wrap">
        <p className="landing-login-label">Create your account</p>
        {returnState?.from?.pathname === "/org/create" && (
          <p className="enter-code-alt" style={{ marginBottom: "1rem" }}>
            Create an account to continue setting up your organization
            {returnState.from.search?.includes("plan=")
              ? " and chosen plan"
              : ""}
            .
          </p>
        )}
        <Form route="/api/user/register/" method="register" />
      </div>
      <p className="enter-code-alt register-back">
        Already have an account?{" "}
        <Link to="/" state={returnState}>
          Sign in
        </Link>
        {" · "}
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}

export default Register;
