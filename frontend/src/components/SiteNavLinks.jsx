import { useState } from "react";
import { Link } from "react-router-dom";
import { NAV_LINKS } from "../constants/siteLinks";
import { HomeIcon } from "./NavIcons";

function NavLinkContent({ item }) {
  if (item.icon === "home") {
    return (
      <>
        <HomeIcon className="landing-nav-icon" />
        <span className="landing-nav-sr-only">{item.label}</span>
      </>
    );
  }
  return item.label;
}

function NavDropdown({ item }) {
  const [open, setOpen] = useState(false);
  const menuId = `nav-menu-${item.label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <div
      className={`landing-nav-dropdown${open ? " landing-nav-dropdown--open" : ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="landing-nav-pill landing-nav-pill--dropdown"
        aria-expanded={open}
        aria-haspopup="true"
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        {item.label}
      </button>
      <ul id={menuId} className="landing-nav-dropdown-menu" role="menu">
        {item.children.map((child) => (
          <li key={child.to} role="none">
            <Link
              className="landing-nav-dropdown-link"
              to={child.to}
              role="menuitem"
              onClick={() => setOpen(false)}
            >
              {child.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function SiteNavLinks() {
  return (
    <nav className="landing-nav-links" aria-label="Main navigation">
      {NAV_LINKS.map((item) => {
        if (item.children) {
          return <NavDropdown key={item.label} item={item} />;
        }

        const className = [
          "landing-nav-pill",
          item.icon === "home" ? "landing-nav-pill--icon" : "",
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
          <Link
            key={item.label}
            className={className}
            to={item.to}
            aria-label={item.icon === "home" ? item.label : undefined}
            title={item.icon === "home" ? item.label : undefined}
          >
            <NavLinkContent item={item} />
          </Link>
        );
      })}
    </nav>
  );
}
