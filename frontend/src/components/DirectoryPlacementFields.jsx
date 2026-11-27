import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../api";

const SCOPE_OPTIONS = [
  { value: "international", label: "Global / International" },
  { value: "national", label: "National" },
  { value: "state_province", label: "State / Province" },
  { value: "local", label: "Local (County)" },
];

const emptyPlacement = {
  geographic_scope: "local",
  country_id: null,
  state_id: null,
  county_id: null,
  primary_category_id: null,
  primary_subcategory_id: null,
};

/**
 * Cascading location + category picker for Explore Communities placement.
 * Controlled via `value` / `onChange` with ids used by the create/placement APIs.
 */
export default function DirectoryPlacementFields({
  value,
  onChange,
  idPrefix = "placement",
  showPreview = true,
}) {
  const placement = { ...emptyPlacement, ...value };
  const [countries, setCountries] = useState([]);
  const [states, setStates] = useState([]);
  const [counties, setCounties] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [loadError, setLoadError] = useState("");

  const setField = useCallback(
    (patch) => {
      onChange({ ...placement, ...patch });
    },
    [onChange, placement]
  );

  useEffect(() => {
    api
      .get("/api/directory/geo/", { params: { area_type: "country", limit: 300 } })
      .then((res) => setCountries(res.data.results || []))
      .catch(() => setLoadError("Could not load countries."));
    api
      .get("/api/directory/categories/")
      .then((res) => setCategories(res.data.categories || res.data.results || []))
      .catch(() => setLoadError("Could not load categories."));
  }, []);

  useEffect(() => {
    if (!placement.country_id) {
      setStates([]);
      return;
    }
    api
      .get("/api/directory/geo/", {
        params: {
          area_type: "state",
          parent_id: placement.country_id,
          limit: 500,
        },
      })
      .then((res) => setStates(res.data.results || []))
      .catch(() => setStates([]));
  }, [placement.country_id]);

  useEffect(() => {
    if (!placement.state_id) {
      setCounties([]);
      return;
    }
    api
      .get("/api/directory/geo/", {
        params: {
          area_type: "county",
          parent_id: placement.state_id,
          limit: 500,
        },
      })
      .then((res) => setCounties(res.data.results || []))
      .catch(() => setCounties([]));
  }, [placement.state_id]);

  useEffect(() => {
    const cat = categories.find((c) => c.id === placement.primary_category_id);
    if (!cat?.slug) {
      setSubcategories([]);
      return;
    }
    api
      .get("/api/directory/categories/", { params: { parent: cat.slug } })
      .then((res) => setSubcategories(res.data.categories || res.data.results || []))
      .catch(() => setSubcategories([]));
  }, [categories, placement.primary_category_id]);

  const needsCountry = ["national", "state_province", "local"].includes(
    placement.geographic_scope
  );
  const needsState = ["state_province", "local"].includes(placement.geographic_scope);
  const needsCounty = placement.geographic_scope === "local";

  const preview = useMemo(() => {
    const country = countries.find((c) => c.id === placement.country_id);
    const state = states.find((s) => s.id === placement.state_id);
    const county = counties.find((c) => c.id === placement.county_id);
    const category = categories.find((c) => c.id === placement.primary_category_id);
    const subcategory = subcategories.find(
      (c) => c.id === placement.primary_subcategory_id
    );
    const geo = [country?.name, state?.name, county?.name].filter(Boolean);
    const cats = [category?.name, subcategory?.name].filter(Boolean);
    if (!geo.length && !cats.length) return null;
    const place = geo[geo.length - 1] || geo.join(" → ");
    if (place && cats.length) return `${place} • ${cats.join(" → ")}`;
    if (cats.length) return cats.join(" → ");
    return geo.join(" → ");
  }, [countries, states, counties, categories, subcategories, placement]);

  return (
    <div className="directory-placement-fields">
      {loadError && <p className="dashboard-error">{loadError}</p>}

      <fieldset className="directory-placement-fieldset">
        <legend>Location</legend>
        <div className="create-org-field">
          <label htmlFor={`${idPrefix}-scope`}>Geographic scope</label>
          <select
            id={`${idPrefix}-scope`}
            value={placement.geographic_scope}
            onChange={(e) =>
              setField({
                geographic_scope: e.target.value,
                country_id: null,
                state_id: null,
                county_id: null,
              })
            }
          >
            {SCOPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {needsCountry && (
          <div className="create-org-field">
            <label htmlFor={`${idPrefix}-country`}>Country</label>
            <select
              id={`${idPrefix}-country`}
              value={placement.country_id || ""}
              onChange={(e) =>
                setField({
                  country_id: e.target.value ? Number(e.target.value) : null,
                  state_id: null,
                  county_id: null,
                })
              }
              required
            >
              <option value="">Select country…</option>
              {countries.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {needsState && (
          <div className="create-org-field">
            <label htmlFor={`${idPrefix}-state`}>State</label>
            <select
              id={`${idPrefix}-state`}
              value={placement.state_id || ""}
              onChange={(e) =>
                setField({
                  state_id: e.target.value ? Number(e.target.value) : null,
                  county_id: null,
                })
              }
              required
              disabled={!placement.country_id}
            >
              <option value="">Select state…</option>
              {states.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {needsCounty && (
          <div className="create-org-field">
            <label htmlFor={`${idPrefix}-county`}>County</label>
            <select
              id={`${idPrefix}-county`}
              value={placement.county_id || ""}
              onChange={(e) =>
                setField({
                  county_id: e.target.value ? Number(e.target.value) : null,
                })
              }
              required
              disabled={!placement.state_id}
            >
              <option value="">Select county…</option>
              {counties.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </fieldset>

      <fieldset className="directory-placement-fieldset">
        <legend>Category</legend>
        <div className="create-org-field">
          <label htmlFor={`${idPrefix}-category`}>Primary category</label>
          <select
            id={`${idPrefix}-category`}
            value={placement.primary_category_id || ""}
            onChange={(e) =>
              setField({
                primary_category_id: e.target.value ? Number(e.target.value) : null,
                primary_subcategory_id: null,
              })
            }
            required
          >
            <option value="">Select category…</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="create-org-field">
          <label htmlFor={`${idPrefix}-subcategory`}>Subcategory</label>
          <select
            id={`${idPrefix}-subcategory`}
            value={placement.primary_subcategory_id || ""}
            onChange={(e) =>
              setField({
                primary_subcategory_id: e.target.value
                  ? Number(e.target.value)
                  : null,
              })
            }
            required
            disabled={!placement.primary_category_id}
          >
            <option value="">Select subcategory…</option>
            {subcategories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      {showPreview && preview && (
        <div className="directory-placement-preview" role="status">
          <p className="directory-placement-preview-label">
            Your organization will appear under:
          </p>
          <p className="directory-placement-preview-value">{preview}</p>
        </div>
      )}
    </div>
  );
}

export function placementFromApi(directoryPlacement) {
  if (!directoryPlacement) return { ...emptyPlacement };
  return {
    geographic_scope: directoryPlacement.geographic_scope || "local",
    country_id: directoryPlacement.country?.id || null,
    state_id: directoryPlacement.state?.id || null,
    county_id: directoryPlacement.county?.id || null,
    primary_category_id: directoryPlacement.primary_category?.id || null,
    primary_subcategory_id: directoryPlacement.primary_subcategory?.id || null,
  };
}

export function placementToApiPayload(placement) {
  return {
    geographic_scope: placement.geographic_scope,
    country_id: placement.country_id,
    state_id: placement.state_id,
    county_id: placement.county_id,
    primary_subcategory_id: placement.primary_subcategory_id,
  };
}
