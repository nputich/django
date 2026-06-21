import { Link } from "react-router-dom";
import Form from "../components/Form";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

function Register() {
  return (
    <MarketingLayout
      showLogin={false}
      mainClassName="landing-main landing-main--centered"
    >
      <SiteLogo variant="compact" />
      <div className="landing-login-wrap">
        <p className="landing-login-label">Create your account</p>
        <Form route="/api/user/register/" method="register" />
      </div>
      <p className="enter-code-alt register-back">
        Already have an account? <Link to="/">Sign in</Link>
        {" · "}
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}

export default Register;
