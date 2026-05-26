import { Link } from "react-router-dom";
import Form from "../components/Form";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

function Register() {
  return (
    <div className="landing">
      <main className="landing-main landing-main--centered">
        <div className="landing-login-wrap">
          <p className="landing-login-label">Create your account</p>
          <Form route="/api/user/register/" method="register" />
        </div>
        <p className="enter-code-alt register-back">
          <Link to="/">← Back to home</Link>
        </p>
      </main>
    </div>
  );
}

export default Register;
