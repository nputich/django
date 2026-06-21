import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import { normalizeAccessCode } from "../accessCode";

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 300;

function isCanceledRequest(err) {
  return (
    axios.isCancel(err) ||
    err?.name === "AbortError" ||
    err?.name === "CanceledError" ||
    err?.code === "ERR_CANCELED"
  );
}

export default function CodeLookup({ className = "" }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();
  const searchSeqRef = useRef(0);
  const abortRef = useRef(null);

  const runSearch = useCallback(async (searchQuery) => {
    const trimmed = searchQuery.trim();

    if (trimmed.length < MIN_QUERY_LENGTH) {
      searchSeqRef.current += 1;
      abortRef.current?.abort();
      setResults([]);
      setError("");
      setHasSearched(false);
      setLoading(false);
      return;
    }

    const seq = ++searchSeqRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError("");

    try {
      const res = await api.get(
        `/api/codes/${encodeURIComponent(trimmed)}/resolve/`,
        { signal: controller.signal }
      );
      if (seq !== searchSeqRef.current) return;
      setResults(res.data.results ?? []);
      setHasSearched(true);
      setError("");
    } catch (err) {
      if (seq !== searchSeqRef.current || isCanceledRequest(err)) return;
      setResults([]);
      setHasSearched(true);
      if (!err.response) {
        setError("Could not reach the server. Check that the backend is running.");
      } else {
        setError(err.response?.data?.detail || "Could not search codes.");
      }
    } finally {
      if (seq === searchSeqRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      runSearch(query);
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
    };
  }, [query, runSearch]);

  useEffect(() => {
    return () => {
      searchSeqRef.current += 1;
      abortRef.current?.abort();
    };
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    runSearch(query);
  };

  const handleSelect = (item) => {
    navigate(item.path);
  };

  const showNoResults =
    hasSearched &&
    !loading &&
    query.trim().length >= MIN_QUERY_LENGTH &&
    results.length === 0 &&
    !error;

  return (
    <div className={`landing-code-lookup ${className}`.trim()}>
      <form className="landing-code-form" onSubmit={handleSubmit}>
        <input
          type="search"
          className="landing-code-input"
          placeholder="Enter community or organization code"
          value={query}
          onChange={(e) => setQuery(normalizeAccessCode(e.target.value))}
          aria-label="Code"
          aria-autocomplete="list"
          aria-controls="code-results-list"
        />
        <button
          type="submit"
          className="landing-code-button"
          disabled={loading || query.trim().length < MIN_QUERY_LENGTH}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
      <p className="landing-code-help">
        <Link to="/search-another-way">Search another way</Link>
      </p>
      {error && <p className="landing-code-error">{error}</p>}
      {showNoResults && <p className="landing-code-error">No results.</p>}
      {results.length > 0 && (
        <div className="code-results" aria-live="polite">
          <p className="code-results-heading">
            {results.length} match{results.length === 1 ? "" : "es"}
          </p>
          <ul className="code-results-list" id="code-results-list">
            {results.map((item) => (
              <li key={item.target_id}>
                <button
                  type="button"
                  className="code-results-item"
                  onClick={() => handleSelect(item)}
                >
                  <span className="code-results-top">
                    <strong>{item.code || item.label}</strong>
                    <span className="code-results-type">{item.type}</span>
                  </span>
                  {item.code && item.label !== item.code && (
                    <span className="code-results-desc">{item.label}</span>
                  )}
                  {item.description &&
                    item.description !== item.label && (
                      <span className="code-results-desc">{item.description}</span>
                    )}
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
