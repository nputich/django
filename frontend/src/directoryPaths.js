/**
 * Parse / build /communities URL paths.
 *
 * Grammar:
 *   /communities
 *   /communities/international
 *   /communities/national/:country
 *   /communities/state_province/:country/:state
 *   /communities/local/:country/:state/:county
 *   /communities/city/:country/:state/:county/:locality
 *   … optional /cat/:category[/:subcategory]
 */

export const SCOPES = new Set([
  "international",
  "national",
  "state_province",
  "local",
  "city",
]);

export const BROWSE_LEVELS = [
  { value: "national", label: "National" },
  { value: "state", label: "State" },
  { value: "county", label: "Local" },
];

export const GLOBAL_COUNTRY = {
  id: "global",
  slug: "global",
  name: "Global",
  area_type: "global",
};

/** Map UI browse level → directory scope used in URLs / API. */
export function scopeForBrowseLevel(browseLevel) {
  if (browseLevel === "national") return "national";
  if (browseLevel === "state") return "state_province";
  if (browseLevel === "county") return "local";
  return "national";
}

export function browseLevelFromScope(scope) {
  if (scope === "national") return "national";
  if (scope === "state_province") return "state";
  if (scope === "local" || scope === "city") return "county";
  return "national";
}

export function parseDirectoryPath(pathname) {
  const parts = pathname.replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
  const result = {
    scope: "",
    country: "",
    state: "",
    county: "",
    locality: "",
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
    result.state = geoParts[1] || "";
  } else if (scope === "local") {
    result.country = geoParts[0] || "";
    result.state = geoParts[1] || "";
    result.county = geoParts[2] || "";
  } else if (scope === "city") {
    result.country = geoParts[0] || "";
    result.state = geoParts[1] || "";
    result.county = geoParts[2] || "";
    result.locality = geoParts[3] || "";
  }

  result.category = catParts[0] || "";
  result.subcategory = catParts[1] || "";
  return result;
}

export function buildDirectoryPath({
  scope = "",
  country = "",
  state = "",
  county = "",
  locality = "",
  category = "",
  subcategory = "",
} = {}) {
  if (!scope) return "/communities";
  const parts = ["/communities", scope];

  if (scope === "national" && country) {
    parts.push(country);
  } else if (scope === "state_province") {
    if (country) parts.push(country);
    if (country && state) parts.push(state);
  } else if (scope === "local") {
    if (country) parts.push(country);
    if (country && state) parts.push(state);
    if (country && state && county) parts.push(county);
  } else if (scope === "city") {
    if (country) parts.push(country);
    if (country && state) parts.push(state);
    if (country && state && county) parts.push(county);
    if (country && state && county && locality) parts.push(locality);
  }

  if (category) {
    parts.push("cat", category);
    if (subcategory) parts.push(subcategory);
  }
  return parts.join("/");
}

export function geoComplete(state) {
  if (!state.scope) return false;
  if (state.scope === "international") return true;
  if (state.scope === "national") return Boolean(state.country);
  if (state.scope === "state_province") {
    return Boolean(state.country && state.state);
  }
  if (state.scope === "local") {
    return Boolean(state.country && state.state && state.county);
  }
  if (state.scope === "city") {
    return Boolean(
      state.country && state.state && state.county && state.locality
    );
  }
  return false;
}
