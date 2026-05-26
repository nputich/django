import { Link } from "react-router-dom";
import Form from "../components/Form";
import "../styles/Landing.css";

function Register() {
  return (
    <div className="landing">
      <section className="landing-login">
        <Form route="/api/user/register/" method="register" />
      </section>
      <p className="landing-footer enter-code-alt">
        <Link to="/">← Back to home</Link>
      </p>
    </div>
  );
}

export default Register;