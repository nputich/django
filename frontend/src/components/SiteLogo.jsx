import { Link } from "react-router-dom";
import wordmarkSvg from "../assets/logo-communibetter.svg?raw";

/** Same wordmark on every page so alignment stays consistent. */
export default function SiteLogo({
  className = "",
  linkHome = true,
  withTagline = false,
}) {
  const label = withTagline
    ? "communiBetter — Build better communities."
    : "communiBetter";

  const image = (
    <span
      className={`landing-logo ${className}`.trim()}
      role="img"
      aria-label={label}
      dangerouslySetInnerHTML={{ __html: wordmarkSvg }}
    />
  );

  const mark = linkHome ? (
    <Link to="/" className="site-logo-link" aria-label="communiBetter home">
      {image}
    </Link>
  ) : (
    image
  );

  return (
    <div className="landing-logo-wrap">
      {mark}
      {withTagline ? (
        <p className="landing-logo-tagline">Build better communities.</p>
      ) : null}
    </div>
  );
}
