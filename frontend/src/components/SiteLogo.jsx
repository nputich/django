import { Link } from "react-router-dom";
import logo from "../assets/logo-communib.png";

/** communiB mark — same hero size on all marketing pages. */
export default function SiteLogo({ className = "", linkHome = true }) {
  const image = (
    <img
      src={logo}
      alt="communiB — Better communities start here"
      className={`landing-logo ${className}`.trim()}
    />
  );

  return (
    <div className="landing-logo-wrap">
      {linkHome ? (
        <Link to="/" className="site-logo-link" aria-label="communiB home">
          {image}
        </Link>
      ) : (
        image
      )}
    </div>
  );
}
