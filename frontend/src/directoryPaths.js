/**
 * Parse / build /communities URL paths.
 *
 * Grammar:
 *   /communities
 *   /communities/:scope
 *   /communities/:scope/:country
 *   /communities/:scope/:country/:admin1
 *   /communities/:scope/:country/:admin1/:admin2
 *   … optional /cat/:category[/:subcategory]
 */

const SCOPES = new Set(["international", "national", "state_province", "local"]);

export function parseDirectoryPath(pathname) {
  const parts = pathname.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
  // parts[0] === "communities"
  const result = {
    scope: "",
    country: "",
    admin1: "",
    admin2: "",
    category: "",
    subcategory: "",
  };
  if (parts[0] !== "communities") return result;

  const scope = parts[1] || "";
  if (!SCOPES.has(scope)) return result;
  result.scope = scope;

  const rest = parts.slice(2);
  const catIndex = rest.indexOf("cat");
  const geoParts = catIndex >= 0 ? rest.slice(0, catIndex) : rest;
  const catParts = catIndex >= 0 ? rest.slice(catIndex + 1) : [];

  if (scope === "international") {
    // no geo segments
  } else if (scope === "national") {
    result.country = geoParts[0] || "";
  } else if (scope === "state_province") {
    result.country = geoParts[0] || "";
    result.admin1 = geoParts[1] || "";
  } else if (scope === "local") {
    result.country = geoParts[0] || "";
    result.admin1 = geoParts[1] || "";
    result.admin2 = geoParts[2] || "";
  }

  result.category = catParts[0] || "";
  result.subcategory = catParts[1] || "";
  return result;
}

export function buildDirectoryPath({
  scope = "",
  country = "",
  admin1 = "",
  admin2 = "",
  category = "",
  subcategory = "",
} = {}) {
  if (!scope) return "/communities";
  const parts = ["/communities", scope];

  if (scope === "national" && country) {
    parts.push(country);
  } else if (scope === "state_province") {
    if (country) parts.push(country);
    if (country && admin1) parts.push(admin1);
  } else if (scope === "local") {
    if (country) parts.push(country);
    if (country && admin1) parts.push(admin1);
    if (country && admin1 && admin2) parts.push(admin2);
  }

  if (category) {
    parts.push("cat", category);
    if (subcategory) parts.push(subcategory);
  }
  return parts.join("/");
}

export function geoComplete(state, scopesMeta) {
  if (!state.scope) return false;
  const meta = scopesMeta.find((s) => s.value === state.scope);
  if (!meta) return false;
  const steps = meta.geo_steps || [];
  if (steps.includes("country") && !state.country) return false;
  if (steps.includes("admin1") && !state.admin1) return false;
  if (steps.includes("admin2") && !state.admin2) return false;
  return true;
}
