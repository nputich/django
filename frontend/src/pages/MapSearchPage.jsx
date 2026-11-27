import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/MapSearch.css";

const markerIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function formatSubs(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function resultKey(m) {
  return `${m.membership_id}-${m.channel_id || "x"}`;
}

function MemberCard({ member }) {
  if (!member) return null;
  const tags = member.tags || member.topics || [];
  return (
    <div className="map-search-card">
      <h3>
        {member.channel_title || member.display_name || member.username}{" "}
        <span className="dashboard-meta">@{member.username}</span>
      </h3>
      {member.communibetter_id && (
        <p className="dashboard-meta">
          <Link to={`/u/${encodeURIComponent(member.username)}`}>
            {member.communibetter_id}
          </Link>
        </p>
      )}
      <p className="dashboard-meta">
        {[member.state, member.zip_code].filter(Boolean).join(" · ")}
      </p>
      {tags.length > 0 && (
        <p className="map-search-tags">
          {tags.map((t) => (
            <span key={t} className="map-search-tag">
              {t}
            </span>
          ))}
        </p>
      )}
      <p>
        <strong>{formatSubs(member.subscriber_count)}</strong> subscribers
        {" · "}
        <strong>{formatSubs(member.video_count)}</strong> videos
      </p>
      <ul className="map-search-channels">
        {(member.youtube_channels || []).map((ch) => (
          <li key={ch.channel_id}>
            <a href={ch.url} target="_blank" rel="noopener noreferrer">
              {ch.title || ch.channel_id}
            </a>
          </li>
        ))}
      </ul>
      <Link
        className="dashboard-btn dashboard-btn--primary"
        to={`/dashboard/inbox?to=${encodeURIComponent(member.username)}`}
      >
        Message
      </Link>
    </div>
  );
}

export default function MapSearchPage() {
  const { slug } = useParams();
  const [view, setView] = useState("map");
  const [me, setMe] = useState(null);
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    tags: "",
    state: "",
    zip_code: "",
  });
  const [joining, setJoining] = useState(false);
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersLayer = useRef(null);

  const runSearch = useCallback(
    async (nextFilters = filters) => {
      const params = {};
      if (nextFilters.state?.trim()) params.state = nextFilters.state.trim();
      if (nextFilters.zip_code?.trim()) {
        params.zip_code = nextFilters.zip_code.trim();
      }
      if (nextFilters.tags?.trim()) params.tags = nextFilters.tags.trim();
      try {
        const res = await api.get(
          `/api/organizations/${slug}/discovery/search/`,
          { params }
        );
        const next = res.data.results || [];
        setResults(next);
        setSelected((prev) => {
          if (!prev) return null;
          const still = next.find((m) => resultKey(m) === resultKey(prev));
          return still || null;
        });
      } catch (err) {
        if (err.response?.status !== 403) {
          setError("Search failed.");
        }
        setResults([]);
        setSelected(null);
      }
    },
    [slug, filters]
  );

  const loadMe = useCallback(async () => {
    try {
      const res = await api.get(`/api/organizations/${slug}/discovery/me/`);
      setMe(res.data);
      setError("");
      return true;
    } catch (err) {
      if (err.response?.status === 403) {
        setMe({ is_member: false });
        setError(
          err.response?.data?.detail ||
            "Join this organization to use Map Search."
        );
        return false;
      }
      if (err.response?.status === 404) {
        setError("Map Search is not enabled for this organization.");
        return false;
      }
      setError("Could not load Map Search.");
      return false;
    }
  }, [slug]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const metaRes = await api.get(`/api/organizations/${slug}/discovery/`);
        if (cancelled) return;
        if (!metaRes.data.discovery_enabled) {
          setError("Map Search is not enabled for this organization.");
          return;
        }
        const ok = await loadMe();
        if (cancelled || !ok) return;
        await runSearch({ tags: "", state: "", zip_code: "" });
      } catch {
        if (!cancelled) setError("Could not load Map Search.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // Keep the map DOM mounted; hide it in list view so Leaflet is not destroyed.
  useEffect(() => {
    if (!mapRef.current) return undefined;

    if (!mapInstance.current) {
      mapInstance.current = L.map(mapRef.current).setView([39.5, -98.35], 4);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 18,
      }).addTo(mapInstance.current);
      markersLayer.current = L.layerGroup().addTo(mapInstance.current);
    }

    const layer = markersLayer.current;
    layer.clearLayers();

    // Group by rounded coords so same ZIP/state pins don't fully stack.
    const groups = new Map();
    results.forEach((m) => {
      if (m.lat == null || m.lng == null) return;
      const key = `${Number(m.lat).toFixed(4)},${Number(m.lng).toFixed(4)}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(m);
    });

    const bounds = [];
    groups.forEach((members) => {
      const baseLat = members[0].lat;
      const baseLng = members[0].lng;
      members.forEach((m, i) => {
        // Spread co-located channels in a small ring (~150–400m).
        let lat = baseLat;
        let lng = baseLng;
        if (members.length > 1) {
          const angle = (2 * Math.PI * i) / members.length - Math.PI / 2;
          const radius = 0.012 + Math.floor(i / 8) * 0.006;
          lat = baseLat + radius * Math.cos(angle);
          lng = baseLng + radius * Math.sin(angle);
        }
        const marker = L.marker([lat, lng], { icon: markerIcon });
        marker.on("click", () => setSelected(m));
        marker.bindTooltip(
          m.channel_title || m.display_name || m.username
        );
        layer.addLayer(marker);
        bounds.push([lat, lng]);
      });
    });

    if (bounds.length) {
      mapInstance.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    } else {
      mapInstance.current.setView([39.5, -98.35], 4);
    }

    if (view === "map") {
      setTimeout(() => mapInstance.current?.invalidateSize(), 50);
    }

    return undefined;
  }, [view, results]);

  useEffect(() => {
    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
        markersLayer.current = null;
      }
    };
  }, []);

  const handleJoin = async () => {
    setJoining(true);
    setError("");
    try {
      await api.post(`/api/organizations/${slug}/join/`);
      await loadMe();
      await runSearch({ tags: "", state: "", zip_code: "" });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not join organization.");
    } finally {
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard">
        <AppHeader />
        <main className="dashboard-main">
          <p className="dashboard-empty">Loading Map Search…</p>
        </main>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main map-search-page">
        <Link to={`/org/${slug}/hub`} className="dashboard-back">
          ← Back to hub
        </Link>
        <h1>Map Search</h1>
        <p className="dashboard-meta">
          Find member channels by tag and location. Connect YouTube and set each
          channel&apos;s state, ZIP, and tags in{" "}
          <Link to="/account#youtube-channels">Account settings</Link>.
        </p>

        {error && <p className="dashboard-error">{error}</p>}

        {me && me.is_member === false && (
          <div className="dashboard-card">
            <p>Join this organization to use Map Search.</p>
            <button
              type="button"
              className="dashboard-btn dashboard-btn--primary"
              onClick={handleJoin}
              disabled={joining}
            >
              {joining ? "Joining…" : "Join organization"}
            </button>
            <p className="dashboard-meta" style={{ marginTop: "0.75rem" }}>
              Or open the <Link to={`/org/${slug}/hub`}>public hub</Link>.
            </p>
          </div>
        )}

        {me?.is_member !== false && me && !me.listed && (
          <p className="dashboard-meta">
            You are not on the map yet. In{" "}
            <Link to="/account#youtube-channels">Account settings</Link>, connect
            YouTube and save a state (and optional ZIP/tags) on at least one
            channel.
          </p>
        )}

        {me?.is_member !== false && (
          <>
            <div className="map-search-toolbar">
              <div className="map-search-filters">
                <div className="map-search-loc-filters">
                  <input
                    value={filters.tags}
                    onChange={(e) =>
                      setFilters((p) => ({ ...p, tags: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        runSearch({ ...filters, tags: e.target.value });
                      }
                    }}
                    placeholder="Tags (comma-separated)"
                    aria-label="Filter tags"
                  />
                  <input
                    value={filters.state}
                    onChange={(e) =>
                      setFilters((p) => ({ ...p, state: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        runSearch({ ...filters, state: e.target.value });
                      }
                    }}
                    placeholder="State"
                    aria-label="Filter state"
                  />
                  <input
                    value={filters.zip_code}
                    onChange={(e) =>
                      setFilters((p) => ({ ...p, zip_code: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        runSearch({ ...filters, zip_code: e.target.value });
                      }
                    }}
                    placeholder="ZIP"
                    aria-label="Filter ZIP"
                  />
                  <button
                    type="button"
                    className="dashboard-btn dashboard-btn--primary"
                    onClick={() => runSearch(filters)}
                  >
                    Search
                  </button>
                </div>
              </div>
              <div
                className="map-search-view-toggle"
                role="group"
                aria-label="View"
              >
                <button
                  type="button"
                  className={view === "map" ? "is-active" : ""}
                  onClick={() => setView("map")}
                >
                  Map
                </button>
                <button
                  type="button"
                  className={view === "list" ? "is-active" : ""}
                  onClick={() => setView("list")}
                >
                  List
                </button>
              </div>
            </div>

            <p className="dashboard-meta map-search-count">
              {results.length === 0
                ? "No channels match these filters."
                : `${results.length} channel${results.length === 1 ? "" : "s"} found — click a pin or list row for details.`}
            </p>

            <div className="map-search-layout">
              <div className="map-search-main">
                <div
                  ref={mapRef}
                  className="map-search-map"
                  hidden={view !== "map"}
                />
                {view === "list" && (
                  <ul className="map-search-list">
                    {results.length === 0 && (
                      <li className="dashboard-empty">No channels match.</li>
                    )}
                    {results.map((m) => (
                      <li key={resultKey(m)}>
                        <button
                          type="button"
                          className={`map-search-list-item${
                            selected && resultKey(selected) === resultKey(m)
                              ? " is-selected"
                              : ""
                          }`}
                          onClick={() => setSelected(m)}
                        >
                          <strong>
                            {m.channel_title || m.display_name || m.username}
                          </strong>
                          <span className="dashboard-meta">
                            @{m.username}
                            {m.communibetter_id
                              ? ` · ${m.communibetter_id}`
                              : ""}
                          </span>
                          <span className="dashboard-meta">
                            {[m.state, m.zip_code].filter(Boolean).join(" · ")} ·{" "}
                            {formatSubs(m.subscriber_count)} subs
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <aside className="map-search-side" aria-label="Selected channel">
                <h2 className="map-search-side-title">Selected channel</h2>
                {selected ? (
                  <MemberCard member={selected} />
                ) : (
                  <p className="dashboard-empty">
                    Select a pin or list row to see details here. Search results
                    appear on the map or in the list on the left.
                  </p>
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
