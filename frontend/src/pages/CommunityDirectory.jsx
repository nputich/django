import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api from "../api";
import MarketingLayout from "../components/MarketingLayout";
import SearchableSelect from "../components/SearchableSelect";
import SiteLogo from "../components/SiteLogo";
import {
  buildDirectoryPath,
  geoComplete,
  parseDirectoryPath,
} from "../directoryPaths";
import "../styles/Landing.css";
import "../styles/Directory.css";

const DEBOUNCE_MS = 250;

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

  const [scopes, setScopes] = useState([]);
  const [countries, setCountries] = useState([]);
  const [admin1Options, setAdmin1Options] = useState([]);
  const [admin2Options, setAdmin2Options] = useState([]);
  const [categories, setCategories] = useState([]);
  const [subcategories, setSubcategories] = useState([]);

  const [countryObj, setCountryObj] = useState(null);
  const [admin1Obj, setAdmin1Obj] = useState(null);
  const [admin2Obj, setAdmin2Obj] = useState(null);

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

  useEffect(() => {
    api
      .get("/api/directory/scopes/")
      .then((res) => setScopes(res.data.scopes || []))
      .catch(() => setError("Could not load directory scopes."));
  }, []);

  // Resolve selected geo objects + option lists when path changes.
  useEffect(() => {
    let cancelled = false;

    async function loadGeo() {
      setError("");
      if (!pathState.scope || pathState.scope === "international") {
        setCountryObj(null);
        setAdmin1Obj(null);
        setAdmin2Obj(null);
        setCountries([]);
        setAdmin1Options([]);
        setAdmin2Options([]);
        return;
      }

      try {
        const countryRes = await api.get("/api/directory/geo/", {
          params: { area_type: "country", q: "", limit: 100 },
        });
        if (cancelled) return;
        const countryList = countryRes.data.results || [];
        setCountries(countryList);
        const selectedCountry =
          countryList.find((c) => c.slug === pathState.country) || null;
        setCountryObj(selectedCountry);

        if (!selectedCountry || pathState.scope === "national") {
          setAdmin1Obj(null);
          setAdmin2Obj(null);
          setAdmin1Options([]);
          setAdmin2Options([]);
          return;
        }

        const admin1Res = await api.get("/api/directory/geo/", {
          params: {
            area_type: "admin1",
            parent_id: selectedCountry.id,
            q: "",
            limit: 100,
          },
        });
        if (cancelled) return;
        const admin1List = admin1Res.data.results || [];
        setAdmin1Options(admin1List);
        const selectedAdmin1 =
          admin1List.find((a) => a.slug === pathState.admin1) || null;
        setAdmin1Obj(selectedAdmin1);

        if (!selectedAdmin1 || pathState.scope === "state_province") {
          setAdmin2Obj(null);
          setAdmin2Options([]);
          return;
        }

        const admin2Res = await api.get("/api/directory/geo/", {
          params: {
            area_type: "admin2",
            parent_id: selectedAdmin1.id,
            q: "",
            limit: 400,
          },
        });
        if (cancelled) return;
        const admin2List = admin2Res.data.results || [];
        setAdmin2Options(admin2List);
        setAdmin2Obj(
          admin2List.find((a) => a.slug === pathState.admin2) || null
        );
      } catch {
        if (!cancelled) setError("Could not load geographic areas.");
      }
    }

    loadGeo();
    return () => {
      cancelled = true;
    };
  }, [pathState.scope, pathState.country, pathState.admin1, pathState.admin2]);

  const isGeoReady = geoComplete(pathState, scopes);

  // Categories always available once geo is complete (even with zero orgs).
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

  // Organization list / search within current geo (+ optional category path).
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
          admin1: pathState.admin1 || undefined,
          admin2: pathState.admin2 || undefined,
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
    pathState.admin1,
    pathState.admin2,
    pathState.category,
    pathState.subcategory,
    debouncedOrgQuery,
  ]);

  const breadcrumb = orgPayload?.breadcrumb || [];

  const onSelectScope = (scope) => {
    setOrgQuery("");
    go({ scope });
  };

  const onSelectCountry = (area) => {
    setOrgQuery("");
    go({
      scope: pathState.scope,
      country: area?.slug || "",
    });
  };

  const onSelectAdmin1 = (area) => {
    setOrgQuery("");
    go({
      scope: pathState.scope,
      country: pathState.country,
      admin1: area?.slug || "",
    });
  };

  const onSelectAdmin2 = (area) => {
    setOrgQuery("");
    go({
      scope: pathState.scope,
      country: pathState.country,
      admin1: pathState.admin1,
      admin2: area?.slug || "",
    });
  };

  const crumbClick = (index) => {
    const crumb = breadcrumb[index];
    if (!crumb) return;
    setOrgQuery("");
    if (crumb.type === "scope") {
      go({ scope: pathState.scope });
      return;
    }
    if (crumb.type === "country") {
      go({ scope: pathState.scope, country: pathState.country });
      return;
    }
    if (crumb.type === "admin1") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        admin1: pathState.admin1,
      });
      return;
    }
    if (crumb.type === "admin2") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        admin1: pathState.admin1,
        admin2: pathState.admin2,
      });
      return;
    }
    if (crumb.type === "category") {
      go({
        scope: pathState.scope,
        country: pathState.country,
        admin1: pathState.admin1,
        admin2: pathState.admin2,
        category: pathState.category,
      });
    }
  };

  const showGeoSelectors = Boolean(pathState.scope);
  const showDirectoryHome = isGeoReady && !pathState.category;
  const showSubcategories =
    isGeoReady && pathState.category && !pathState.subcategory;
  // Always show search once geo complete.
  const showOrgSearch = isGeoReady;

  const orgs = orgPayload?.organizations || [];
  const emptyMessage = orgPayload?.empty_message;

  return (
    <MarketingLayout mainClassName="landing-main">
      <section className="landing-hero">
        <SiteLogo />
      </section>

      <div className="directory-page">
        <h1 className="directory-title">Explore communities</h1>
        <p className="directory-lead">
          Browse by geography, then search for an organization or explore by
          category.
        </p>

        {breadcrumb.length > 0 && (
          <nav className="directory-breadcrumb" aria-label="Directory location">
            {breadcrumb.map((crumb, index) => (
              <span key={`${crumb.type}-${crumb.value}`}>
                {index > 0 && <span className="directory-breadcrumb-sep">→</span>}
                <button type="button" onClick={() => crumbClick(index)}>
                  {crumb.label}
                </button>
              </span>
            ))}
          </nav>
        )}

        {error && <p className="directory-empty">{error}</p>}

        {!pathState.scope && (
          <section className="directory-section">
            <h2 className="directory-section-title">Choose a geographic scope</h2>
            <div className="directory-scope-grid">
              {scopes.map((scope) => (
                <button
                  key={scope.value}
                  type="button"
                  className="directory-scope-btn"
                  onClick={() => onSelectScope(scope.value)}
                >
                  <strong>{scope.label}</strong>
                  <span>
                    {scope.geo_steps?.length
                      ? `Select ${scope.geo_steps.join(" → ")}`
                      : "Browse international organizations"}
                  </span>
                </button>
              ))}
            </div>
            {/* Regional scope is intentionally hidden until regional areas are seeded. */}
          </section>
        )}

        {showGeoSelectors && pathState.scope !== "international" && (
          <section className="directory-section">
            <h2 className="directory-section-title">Location</h2>
            <div className="directory-stack">
              <SearchableSelect
                label="Country"
                placeholder="Search countries…"
                options={countries}
                value={countryObj}
                onChange={onSelectCountry}
              />
              {(pathState.scope === "state_province" ||
                pathState.scope === "local") &&
                countryObj && (
                  <SearchableSelect
                    label="State / Province / Territory"
                    placeholder="Search states…"
                    options={admin1Options}
                    value={admin1Obj}
                    onChange={onSelectAdmin1}
                  />
                )}
              {pathState.scope === "local" && admin1Obj && (
                <SearchableSelect
                  label="County / County-equivalent"
                  placeholder="Search counties…"
                  options={admin2Options}
                  value={admin2Obj}
                  onChange={onSelectAdmin2}
                />
              )}
            </div>
          </section>
        )}

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
            {debouncedOrgQuery.trim() && !loadingOrgs && (
              <>
                {orgs.length > 0 ? (
                  <ul className="directory-list" style={{ marginTop: "0.85rem" }}>
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
              </>
            )}
          </section>
        )}

        {showDirectoryHome && !debouncedOrgQuery.trim() && (
          <section className="directory-section">
            <h2 className="directory-section-title">Browse by category</h2>
            {!loadingOrgs &&
              orgPayload &&
              orgPayload.total === 0 &&
              !pathState.category && (
                <p className="directory-empty">There are no organizations yet.</p>
              )}
            <ul className="directory-list">
              {categories.map((cat) => (
                <li key={cat.id}>
                  <button
                    type="button"
                    className="directory-link-btn"
                    onClick={() =>
                      go({
                        scope: pathState.scope,
                        country: pathState.country,
                        admin1: pathState.admin1,
                        admin2: pathState.admin2,
                        category: cat.slug,
                      })
                    }
                  >
                    <strong>{cat.name}</strong>
                  </button>
                </li>
              ))}
            </ul>
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
                        scope: pathState.scope,
                        country: pathState.country,
                        admin1: pathState.admin1,
                        admin2: pathState.admin2,
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

        <p className="directory-back-row">
          <Link to="/enter-code">← Enter a community code instead</Link>
        </p>
      </div>
    </MarketingLayout>
  );
}
