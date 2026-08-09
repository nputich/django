import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../api";
import MarketingLayout from "../components/MarketingLayout";
import SearchableSelect from "../components/SearchableSelect";
import SiteLogo from "../components/SiteLogo";
import {
  BROWSE_LEVELS,
  GLOBAL_COUNTRY,
  browseLevelFromScope,
  buildDirectoryPath,
  geoComplete,
  parseDirectoryPath,
  scopeForBrowseLevel,
} from "../directoryPaths";
import "../styles/Landing.css";
import "../styles/Directory.css";

const DEBOUNCE_MS = 250;
const US_SLUG = "us";

function useDebouncedValue(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function CommunityDirectory() {
  const location = useLocation();
  const navigate = useNavigate();
  const pathState = useMemo(
    () => parseDirectoryPath(location.pathname),
    [location.pathname]
  );

  const [countries, setCountries] = useState([]);
  const [stateOptions, setStateOptions] = useState([]);
  const [countyOptions, setCountyOptions] = useState([]);
  const [localityOptions, setLocalityOptions] = useState([]);
  const [loadingState, setLoadingState] = useState(false);
  const [loadingCounty, setLoadingCounty] = useState(false);
  const [loadingLocality, setLoadingLocality] = useState(false);

  const [countryObj, setCountryObj] = useState(null);
  const [stateObj, setStateObj] = useState(null);
  const [countyObj, setCountyObj] = useState(null);
  const [localityObj, setLocalityObj] = useState(null);

  const [stateQuery, setStateQuery] = useState("");
  const [countyQuery, setCountyQuery] = useState("");
  const [localityQuery, setLocalityQuery] = useState("");
  const debouncedStateQuery = useDebouncedValue(stateQuery, DEBOUNCE_MS);
  const debouncedCountyQuery = useDebouncedValue(countyQuery, DEBOUNCE_MS);
  const debouncedLocalityQuery = useDebouncedValue(localityQuery, DEBOUNCE_MS);

  const [categories, setCategories] = useState([]);
  const [subcategories, setSubcategories] = useState([]);

  const [orgQuery, setOrgQuery] = useState("");
  const debouncedOrgQuery = useDebouncedValue(orgQuery, DEBOUNCE_MS);
  const [orgPayload, setOrgPayload] = useState(null);
  const [loadingOrgs, setLoadingOrgs] = useState(false);
  const [error, setError] = useState("");
  const orgAbortRef = useRef(null);

  const go = useCallback(
    (next) => {
      navigate(buildDirectoryPath(next));
    },
    [navigate]
  );

  // Default empty /communities → Global.
  useEffect(() => {
    if (!pathState.scope) {
      navigate(buildDirectoryPath({ scope: "international" }), { replace: true });
    }
  }, [pathState.scope, navigate]);

  const isGlobal = pathState.scope === "international";
  const isUnitedStates = pathState.country === US_SLUG;
  const browseLevel = isGlobal
    ? null
    : browseLevelFromScope(pathState.scope || "national");
  const browseLevelObj =
    BROWSE_LEVELS.find((level) => level.value === browseLevel) || null;

  const showBrowseLevel = Boolean(countryObj && !isGlobal && isUnitedStates);
  const showState =
    showBrowseLevel &&
    (browseLevel === "state" || browseLevel === "county" || browseLevel === "city");
  const showCounty =
    showBrowseLevel && (browseLevel === "county" || browseLevel === "city");
  const showCity = showBrowseLevel && browseLevel === "city";

  // Load countries once.
  useEffect(() => {
    api
      .get("/api/directory/geo/", {
        params: { area_type: "country", q: "", limit: 100 },
      })
      .then((res) => {
        const list = res.data.results || [];
        // Prefer United States first among real countries.
        list.sort((a, b) => {
          if (a.slug === US_SLUG) return -1;
          if (b.slug === US_SLUG) return 1;
          return (a.name || "").localeCompare(b.name || "");
        });
        setCountries(list);
      })
      .catch(() => setError("Could not load countries."));
  }, []);

  // Sync selected country / objects from path.
  useEffect(() => {
    if (isGlobal || !pathState.scope) {
      setCountryObj(GLOBAL_COUNTRY);
      setStateObj(null);
      setCountyObj(null);
      setLocalityObj(null);
      return;
    }
    if (!countries.length) return;
    const selected =
      countries.find((c) => c.slug === pathState.country) || null;
    setCountryObj(selected);
  }, [isGlobal, pathState.scope, pathState.country, countries]);

  // Load / search states when needed.
  useEffect(() => {
    if (!showState || !countryObj?.id || countryObj.id === "global") {
      setStateOptions([]);
      if (!pathState.state) setStateObj(null);
      return;
    }
    let cancelled = false;
    setLoadingState(true);
    api
      .get("/api/directory/geo/", {
        params: {
          area_type: "state",
          parent_id: countryObj.id,
          q: debouncedStateQuery,
          limit: 100,
        },
      })
      .then((res) => {
        if (cancelled) return;
        const list = res.data.results || [];
        setStateOptions(list);
        if (!pathState.state) {
          setStateObj(null);
          return;
        }
        const match = list.find((a) => a.slug === pathState.state);
        if (match) setStateObj(match);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load states.");
      })
      .finally(() => {
        if (!cancelled) setLoadingState(false);
      });
    return () => {
      cancelled = true;
    };
  }, [showState, countryObj?.id, debouncedStateQuery, pathState.state]);

  // Load / search counties.
  useEffect(() => {
    if (!showCounty || !stateObj?.id) {
      setCountyOptions([]);
      if (!pathState.county) setCountyObj(null);
      return;
    }
    let cancelled = false;
    setLoadingCounty(true);
    api
      .get("/api/directory/geo/", {
        params: {
          area_type: "county",
          parent_id: stateObj.id,
          q: debouncedCountyQuery,
          limit: 500,
        },
      })
      .then((res) => {
        if (cancelled) return;
        const list = res.data.results || [];
        setCountyOptions(list);
        const match = list.find((a) => a.slug === pathState.county);
        if (match) setCountyObj(match);
        else if (!pathState.county) setCountyObj(null);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load counties.");
      })
      .finally(() => {
        if (!cancelled) setLoadingCounty(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    showCounty,
    stateObj?.id,
    debouncedCountyQuery,
    pathState.county,
  ]);

  // Load / search cities.
  useEffect(() => {
    if (!showCity || !countyObj?.id) {
      setLocalityOptions([]);
      if (!pathState.locality) setLocalityObj(null);
      return;
    }
    let cancelled = false;
    setLoadingLocality(true);
    api
      .get("/api/directory/geo/", {
        params: {
          area_type: "locality",
          parent_id: countyObj.id,
          q: debouncedLocalityQuery,
          limit: 200,
        },
      })
      .then((res) => {
        if (cancelled) return;
        const list = res.data.results || [];
        setLocalityOptions(list);
        const match = list.find((a) => a.slug === pathState.locality);
        if (match) setLocalityObj(match);
        else if (pathState.locality) {
          setLocalityObj({
            id: `city:${pathState.locality}`,
            slug: pathState.locality,
            name: pathState.locality.replace(/-/g, " "),
            area_type: "locality",
          });
        } else {
          setLocalityObj(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load cities.");
      })
      .finally(() => {
        if (!cancelled) setLoadingLocality(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    showCity,
    countyObj?.id,
    debouncedLocalityQuery,
    pathState.locality,
  ]);

  const isGeoReady = geoComplete(pathState);

  useEffect(() => {
    if (!isGeoReady || pathState.category) {
      if (!pathState.category) setCategories([]);
      return;
    }
    api
      .get("/api/directory/categories/")
      .then((res) => setCategories(res.data.categories || []))
      .catch(() => setError("Could not load categories."));
  }, [isGeoReady, pathState.category]);

  useEffect(() => {
    if (!pathState.category) {
      setSubcategories([]);
      return;
    }
    api
      .get("/api/directory/categories/", {
        params: { parent: pathState.category },
      })
      .then((res) => setSubcategories(res.data.categories || []))
      .catch(() => setError("Could not load subcategories."));
  }, [pathState.category]);

  useEffect(() => {
    if (!isGeoReady) {
      setOrgPayload(null);
      return;
    }

    orgAbortRef.current?.abort();
    const controller = new AbortController();
    orgAbortRef.current = controller;
    setLoadingOrgs(true);

    api
      .get("/api/directory/organizations/", {
        params: {
          scope: pathState.scope,
          country: pathState.country || undefined,
          state: pathState.state || undefined,
          county: pathState.county || undefined,
          locality: pathState.locality || undefined,
          category: pathState.category || undefined,
          subcategory: pathState.subcategory || undefined,
          q: debouncedOrgQuery || undefined,
        },
        signal: controller.signal,
      })
      .then((res) => {
        setOrgPayload(res.data);
        setError("");
      })
      .catch((err) => {
        if (err?.code === "ERR_CANCELED" || err?.name === "CanceledError") return;
        setError(err.response?.data?.detail || "Could not load organizations.");
      })
      .finally(() => setLoadingOrgs(false));

    return () => controller.abort();
  }, [
    isGeoReady,
    pathState.scope,
    pathState.country,
    pathState.state,
    pathState.county,
    pathState.locality,
    pathState.category,
    pathState.subcategory,
    debouncedOrgQuery,
  ]);

  const breadcrumb = orgPayload?.breadcrumb || [];

  const onSelectCountry = (area) => {
    setOrgQuery("");
    if (!area || area.slug === "global") {
      go({ scope: "international" });
      return;
    }
    // Default browse level for a real country is National.
    go({
      scope: "national",
      country: area.slug,
    });
  };

  const onSelectBrowseLevel = (level) => {
    setOrgQuery("");
    const next = level?.value || "national";
    const scope = scopeForBrowseLevel(next);
    go({
      scope,
      country: pathState.country || US_SLUG,
    });
  };

  const onSelectState = (area) => {
    setOrgQuery("");
    go({
      scope: pathState.scope,
      country: pathState.country,
      state: area?.slug || "",
    });
  };

  const onSelectCounty = (area) => {
    setOrgQuery("");
    go({
      scope: pathState.scope,
      country: pathState.country,
      state: pathState.state,
      county: area?.slug || "",
    });
  };

  const onSelectLocality = (area) => {
    setOrgQuery("");
    go({
      scope: "city",
      country: pathState.country,
      state: pathState.state,
      county: pathState.county,
      locality: area?.slug || "",
    });
  };

  const crumbClick = (index) => {
    const crumb = breadcrumb[index];
    if (!crumb) return;
    setOrgQuery("");
    if (crumb.type === "scope") {
      if (pathState.scope === "international") {
        go({ scope: "international" });
      } else {
        go({
          scope: pathState.scope,
          country: pathState.country,
        });
      }
      return;
    }
    if (crumb.type === "country") {
      go({ scope: pathState.scope, country: pathState.country });
      return;
    }
    if (crumb.type === "state") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        state: pathState.state,
      });
      return;
    }
    if (crumb.type === "county") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        state: pathState.state,
        county: pathState.county,
      });
      return;
    }
    if (crumb.type === "locality") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        state: pathState.state,
        county: pathState.county,
        locality: pathState.locality,
      });
      return;
    }
    if (crumb.type === "category") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        state: pathState.state,
        county: pathState.county,
        locality: pathState.locality,
        category: pathState.category,
      });
    }
  };

  const geoNavBase = {
    scope: pathState.scope,
    country: pathState.country,
    state: pathState.state,
    county: pathState.county,
    locality: pathState.locality,
  };

  const showDirectoryHome = isGeoReady && !pathState.category;
  const showSubcategories =
    isGeoReady && pathState.category && !pathState.subcategory;
  const showOrgSearch = isGeoReady;

  const orgs = orgPayload?.organizations || [];
  const emptyMessage = orgPayload?.empty_message;

  const countryOptions = countries;
  const onSearchState = useCallback((q) => setStateQuery(q), []);
  const onSearchCounty = useCallback((q) => setCountyQuery(q), []);
  const onSearchLocality = useCallback((q) => setLocalityQuery(q), []);

  return (
    <MarketingLayout mainClassName="landing-main">
      <section className="landing-hero">
        <SiteLogo />
      </section>

      <div className="directory-page">
        <header className="directory-header">
          <h1 className="directory-title">Explore communities</h1>
          <p className="directory-lead">
            Filter by location, then search for an organization or browse by
            category.
          </p>

          {breadcrumb.length > 0 && (
            <nav className="directory-breadcrumb" aria-label="Directory location">
              {breadcrumb.map((crumb, index) => (
                <span key={`${crumb.type}-${crumb.value}`}>
                  {index > 0 && (
                    <span className="directory-breadcrumb-sep">→</span>
                  )}
                  <button type="button" onClick={() => crumbClick(index)}>
                    {crumb.label}
                  </button>
                </span>
              ))}
            </nav>
          )}

          {error && <p className="directory-empty">{error}</p>}
        </header>

        <div className="directory-layout">
          <aside className="directory-filters" aria-label="Directory filters">
            <section className="directory-filter-block">
              <h2 className="directory-section-title">Find by Location</h2>
              <div className="directory-stack">
                <SearchableSelect
                  label="Country"
                  placeholder="Search countries…"
                  options={countryOptions}
                  pinnedOptions={[GLOBAL_COUNTRY]}
                  value={countryObj || GLOBAL_COUNTRY}
                  onChange={onSelectCountry}
                />

                {showBrowseLevel && (
                  <SearchableSelect
                    label="Browse Level"
                    placeholder="Select browse level…"
                    options={BROWSE_LEVELS}
                    value={browseLevelObj}
                    onChange={onSelectBrowseLevel}
                    getOptionLabel={(o) => o?.label ?? ""}
                    getOptionKey={(o) => o?.value ?? ""}
                  />
                )}

                {showState && (
                  <SearchableSelect
                    label="State"
                    placeholder="Search or select a state…"
                    options={stateOptions}
                    value={stateObj}
                    onChange={onSelectState}
                    onSearch={onSearchState}
                    loading={loadingState}
                    emptyMessage="No matching states"
                  />
                )}

                {showCounty && stateObj && (
                  <SearchableSelect
                    label="County / Region"
                    placeholder="Search counties…"
                    options={countyOptions}
                    value={countyObj}
                    onChange={onSelectCounty}
                    onSearch={onSearchCounty}
                    loading={loadingCounty}
                    emptyMessage="No matching counties"
                  />
                )}

                {showCity && countyObj && (
                  <SearchableSelect
                    label="City / Locality"
                    placeholder="Search cities…"
                    options={localityOptions}
                    value={localityObj}
                    onChange={onSelectLocality}
                    onSearch={onSearchLocality}
                    loading={loadingLocality}
                    emptyMessage="No matching cities yet"
                  />
                )}
              </div>
            </section>

            {isGeoReady && (
              <section className="directory-filter-block">
                <h2 className="directory-section-title">Browse by Category</h2>
                {!pathState.category && (
                  <ul className="directory-list directory-list--compact">
                    {categories.map((cat) => (
                      <li key={cat.id}>
                        <button
                          type="button"
                          className="directory-link-btn"
                          onClick={() =>
                            go({
                              ...geoNavBase,
                              category: cat.slug,
                            })
                          }
                        >
                          <strong>{cat.name}</strong>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {pathState.category && !pathState.subcategory && (
                  <ul className="directory-list directory-list--compact">
                    {subcategories.map((sub) => (
                      <li key={sub.id}>
                        <button
                          type="button"
                          className="directory-link-btn"
                          onClick={() =>
                            go({
                              ...geoNavBase,
                              category: pathState.category,
                              subcategory: sub.slug,
                            })
                          }
                        >
                          <strong>{sub.name}</strong>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {pathState.category && (
                  <button
                    type="button"
                    className="directory-clear-cat"
                    onClick={() => go({ ...geoNavBase })}
                  >
                    ← All categories
                  </button>
                )}
              </section>
            )}
          </aside>

          <div className="directory-results">
            {showOrgSearch && (
              <section className="directory-section">
                <h2 className="directory-section-title">Search organizations</h2>
                <input
                  type="search"
                  className="directory-org-search"
                  placeholder="Search organizations…"
                  value={orgQuery}
                  onChange={(e) => setOrgQuery(e.target.value)}
                  aria-label="Search organizations"
                />
                {loadingOrgs && (
                  <p className="directory-meta">Updating results…</p>
                )}
              </section>
            )}

            {!isGeoReady && pathState.scope && pathState.scope !== "international" && (
              <section className="directory-section">
                <p className="directory-empty">
                  {browseLevel === "state" &&
                    "Select a state to see organizations."}
                  {browseLevel === "county" &&
                    !stateObj &&
                    "Select a state, then a county / region."}
                  {browseLevel === "county" &&
                    stateObj &&
                    !countyObj &&
                    "Select a county / region to see organizations."}
                  {browseLevel === "city" &&
                    "Select state, county / region, then a city / locality."}
                  {browseLevel === "national" &&
                    "Loading national organizations…"}
                </p>
              </section>
            )}

            {showDirectoryHome && !debouncedOrgQuery.trim() && (
              <section className="directory-section">
                <h2 className="directory-section-title">Organizations</h2>
                {!loadingOrgs &&
                  orgPayload &&
                  orgPayload.total === 0 && (
                    <p className="directory-empty">
                      There are no organizations yet.
                    </p>
                  )}
                {!loadingOrgs && orgs.length > 0 && (
                  <ul className="directory-list">
                    {orgs.map((org) => (
                      <li key={org.id}>
                        <button
                          type="button"
                          className="directory-org-btn"
                          onClick={() => navigate(org.path)}
                        >
                          <strong>{org.name}</strong>
                          {org.primary_subcategory && (
                            <span>
                              {org.primary_category?.name}
                              {org.primary_category ? " · " : ""}
                              {org.primary_subcategory.name}
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {debouncedOrgQuery.trim() && isGeoReady && !loadingOrgs && (
              <section className="directory-section">
                <h2 className="directory-section-title">Search results</h2>
                {orgs.length > 0 ? (
                  <ul className="directory-list">
                    {orgs.map((org) => (
                      <li key={org.id}>
                        <button
                          type="button"
                          className="directory-org-btn"
                          onClick={() => navigate(org.path)}
                        >
                          <strong>{org.name}</strong>
                          {org.primary_subcategory && (
                            <span>
                              {org.primary_category?.name}
                              {org.primary_category ? " · " : ""}
                              {org.primary_subcategory.name}
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="directory-empty">
                    {pathState.category || pathState.subcategory
                      ? "There is no group here yet"
                      : "There are no organizations yet."}
                  </p>
                )}
              </section>
            )}

            {showSubcategories && !debouncedOrgQuery.trim() && (
              <section className="directory-section">
                <h2 className="directory-section-title">
                  {orgPayload?.category?.name || "Subcategories"}
                </h2>
                <ul className="directory-list">
                  {subcategories.map((sub) => (
                    <li key={sub.id}>
                      <button
                        type="button"
                        className="directory-link-btn"
                        onClick={() =>
                          go({
                            ...geoNavBase,
                            category: pathState.category,
                            subcategory: sub.slug,
                          })
                        }
                      >
                        <strong>{sub.name}</strong>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {pathState.subcategory && !debouncedOrgQuery.trim() && (
              <section className="directory-section">
                <h2 className="directory-section-title">
                  {orgPayload?.subcategory?.name || "Organizations"}
                </h2>
                {loadingOrgs && <p className="directory-meta">Loading…</p>}
                {!loadingOrgs && orgs.length === 0 && (
                  <p className="directory-empty">
                    {emptyMessage || "There is no group here yet"}
                  </p>
                )}
                {!loadingOrgs && orgs.length > 0 && (
                  <ul className="directory-list">
                    {orgs.map((org) => (
                      <li key={org.id}>
                        <button
                          type="button"
                          className="directory-org-btn"
                          onClick={() => navigate(org.path)}
                        >
                          <strong>{org.name}</strong>
                          {org.description && <span>{org.description}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </div>
        </div>

        <p className="directory-back-row">
          <Link to="/enter-code">← Enter a community code instead</Link>
        </p>
      </div>
    </MarketingLayout>
  );
}
