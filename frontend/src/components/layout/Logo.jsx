import { Link } from "react-router-dom";
import "../../styles/Logo.css";

function Logo() {
  return (
    <Link to="/" className="logo" aria-label="communib home">
      <span className="logo-mark" aria-hidden="true">
        c
      </span>
      <span className="logo-text">communib</span>
    </Link>
  );
}

export default Logo;
