import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
export default function CodeLookup({ className = "" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const handleSearch = async (e) => {
    e.preventDefault();
    setError("");
    setResults([]);
    setLoading(true);
    try {
      const res = await api.get(
        `/api/codes/${encodeURIComponent(query.trim())}/resolve/`
      );
      setResults(res.data.results ?? []);
      if ((res.data.results ?? []).length === 0) {
        setError("No results.");
      }
    } catch (err) {
      setResults([]);
      setError(err.response?.data?.detail || "No results.");
    } finally {
      setLoading(false);
    }
  };
  const handleSelect = (item) => {
    navigate(item.path);
  };
  return (
    <div className={`landing-code-lookup ${className}`.trim()}>
      <form className="landing-code-form" onSubmit={handleSearch}>
        <input
          type="search"
          className="landing-code-input"
          placeholder="Enter community or organization code"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Code"
        />
        <button
          type="submit"
          className="landing-code-button"
          disabled={loading || !query.trim()}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
      <p className="landing-code-help">
        Select a result below to continue.{" "}
        <Link to="/search-another-way">Search another way</Link>
      </p>
      {error && <p className="landing-code-error">{error}</p>}
      {results.length > 0 && (
        <div className="code-results">
          <p className="code-results-heading">
            {results.length} result{results.length === 1 ? "" : "s"} for &ldquo;{query}&rdquo;
          </p>
          <ul className="code-results-list">
            {results.map((item) => (
              <li key={item.target_id}>
                <button
                  type="button"
                  className="code-results-item"
                  onClick={() => handleSelect(item)}
                >
                  <span className="code-results-top">
                    <strong>{item.label}</strong>
                    <span className="code-results-type">{item.type}</span>
                  </span>
                  <span className="code-results-desc">{item.description}</span>
                  {item.organization_name && (
                    <span className="code-results-org">{item.organization_name}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}