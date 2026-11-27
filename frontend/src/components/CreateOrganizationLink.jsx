import { Link, useNavigate } from "react-router-dom";
import { ensureValidSession } from "../auth";
import { createOrganizationPath } from "../constants/orgCreation";

/**
 * Orange “Create an Organization” CTA used across directory, dashboard, pricing.
 * Guests are sent to register first, then returned to `/org/create`.
 */
export default function CreateOrganizationLink({
  plan,
  name,
  children = "Create an Organization",
  className = "create-org-link",
  asButton = false,
}) {
  const navigate = useNavigate();
  const to = createOrganizationPath({ plan, name });
  const classes = [className, asButton ? "create-org-link--button" : null]
    .filter(Boolean)
    .join(" ");

  const handleClick = (e) => {
    if (ensureValidSession()) return;
    e.preventDefault();
    const qIndex = to.indexOf("?");
    const pathname = qIndex >= 0 ? to.slice(0, qIndex) : to;
    const search = qIndex >= 0 ? to.slice(qIndex) : "";
    navigate("/register", {
      state: { from: { pathname, search } },
    });
  };

  return (
    <Link to={to} className={classes} onClick={handleClick}>
      {children}
    </Link>
  );
}
