import { Link } from "react-router-dom";
import { createOrganizationPath } from "../constants/orgCreation";

/**
 * Orange “Create an Organization” CTA used across directory, dashboard, pricing.
 * Always opens the same `/org/create` flow.
 */
export default function CreateOrganizationLink({
  plan,
  name,
  children = "Create an Organization",
  className = "create-org-link",
  asButton = false,
}) {
  const to = createOrganizationPath({ plan, name });
  const classes = [className, asButton ? "create-org-link--button" : null]
    .filter(Boolean)
    .join(" ");
  return (
    <Link to={to} className={classes}>
      {children}
    </Link>
  );
}
