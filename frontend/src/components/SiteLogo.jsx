import { Link } from "react-router-dom";
import logo from "../assets/logo-communib.png";

/**
 * communiB mark for hero and secondary pages.
 * @param {"hero" | "compact"} variant
 */
export default function SiteLogo({ variant = "hero", className = "", linkHome = false }) {
  const wrapClass =
    variant === "hero" ? "landing-logo-wrap" : "site-logo-wrap";
  const imgClass =
    variant === "hero"
      ? `landing-logo ${className}`.trim()
      : `site-logo site-logo--compact ${className}`.trim();

  const image = (
    <img
      src={logo}
      alt="communiB — Better communities start here"
      className={imgClass}
    />
  );

  return (
    <div className={wrapClass}>
      {linkHome || variant === "hero" ? (
        <Link to="/" className="site-logo-link" aria-label="communiB home">
          {image}
        </Link>
      ) : (
        image
      )}
    </div>
  );
}
