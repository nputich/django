import { DONATE_URL, SOCIAL_LINKS } from "../../config/links";
import "../../styles/SiteFooter.css";

function YouTubeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        fill="currentColor"
        d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31.5 31.5 0 0 0 0 12a31.5 31.5 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31.5 31.5 0 0 0 24 12a31.5 31.5 0 0 0-.5-5.8zM9.6 15.6V8.4L15.8 12l-6.2 3.6z"
      />
    </svg>
  );
}

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <a
          href={DONATE_URL}
          className="donate-btn"
          target="_blank"
          rel="noopener noreferrer"
        >
          Support communib
        </a>
        <div className="social-links" aria-label="Social media">
          {SOCIAL_LINKS.map((link) => (
            <a
              key={link.id}
              href={link.href}
              className="social-link"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={link.label}
            >
              {link.id === "youtube" && <YouTubeIcon />}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}

export default SiteFooter;
