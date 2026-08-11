/** Shared path for every “Create an Organization” entry point. */
export const CREATE_ORGANIZATION_PATH = "/org/create";

/** Public pricing / plans page (replaces under-construction `/org`). */
export const ORG_PRICING_PATH = "/org";

export const PAID_PLAN_LEVELS = {
  BASIC: "BASIC",
  COMMUNITY: "COMMUNITY",
  COMMUNITY_PLUS: "COMMUNITY_PLUS",
};

export function createOrganizationPath({ plan, name } = {}) {
  const params = new URLSearchParams();
  if (plan) params.set("plan", plan);
  if (name) params.set("name", name);
  const qs = params.toString();
  return qs ? `${CREATE_ORGANIZATION_PATH}?${qs}` : CREATE_ORGANIZATION_PATH;
}

export function claimAccessPath(org) {
  const params = new URLSearchParams();
  params.set("subject", `Claim access to ${org.name}`);
  params.set(
    "message",
    `I would like to claim admin access to the organization "${org.name}"${
      org.slug ? ` (/${org.slug})` : ""
    }.`
  );
  if (org.slug) params.set("org", org.slug);
  return `/contact?${params.toString()}`;
}
