import { Link } from "react-router-dom";
import { FOOTER_LINKS } from "../constants/siteLinks";

export default function SiteFooter() {
  return (
    <footer className="landing-footer">
      <nav className="landing-footer-links" aria-label="Legal and company">
        {FOOTER_LINKS.map((item) => (
          <Link key={item.to} to={item.to}>
            {item.label}
          </Link>
        ))}
      </nav>
      <p>© {new Date().getFullYear()} communiB</p>
    </footer>
  );
}
