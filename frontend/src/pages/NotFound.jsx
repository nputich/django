import { Link } from "react-router-dom";
import "../styles/Landing.css";
import "../styles/EnterCode.css";

function NotFound() {
  return (
    <div className="enter-code">
      <h1>Page not found</h1>
      <p className="enter-code-subtitle">
        The page you are looking for does not exist.
      </p>
      <p className="enter-code-alt">
        <Link to="/">← Back to home</Link>
      </p>
    </div>
  );
}

export default NotFound;
