import { Link } from "react-router-dom";
import { FOOTER_LINKS } from "../constants/siteLinks";
import { YouTubeIcon } from "./NavIcons";

export default function SiteFooter() {
  return (
    <footer className="landing-footer">
      <nav className="landing-footer-links" aria-label="Legal and company">
        {FOOTER_LINKS.map((item) => {
          if (item.external && item.icon === "youtube") {
            return (
              <a
                key={item.label}
                className="landing-footer-youtube"
                href={item.to}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="communiB on YouTube"
                title="YouTube"
              >
                <YouTubeIcon />
              </a>
            );
          }
          if (item.external) {
            return (
              <a
                key={item.label}
                href={item.to}
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.label}
              </a>
            );
          }
          return (
            <Link key={item.to} to={item.to}>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <p>© {new Date().getFullYear()} communiB</p>
    </footer>
  );
}
