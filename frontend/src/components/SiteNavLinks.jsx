import { Link } from "react-router-dom";
import { NAV_LINKS } from "../constants/siteLinks";

export default function SiteNavLinks() {
  return (
    <nav className="landing-nav-links" aria-label="Main navigation">
      {NAV_LINKS.map((item) => {
        const className = [
          "landing-nav-pill",
          item.primary ? "landing-nav-pill--primary" : "",
        ]
          .filter(Boolean)
          .join(" ");

        if (item.external) {
          return (
            <a
              key={item.label}
              className={className}
              href={item.to}
              target="_blank"
              rel="noopener noreferrer"
            >
              {item.label}
            </a>
          );
        }

        return (
          <Link key={item.label} className={className} to={item.to}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
