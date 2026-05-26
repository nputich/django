import { useState } from "react";
import { Link } from "react-router-dom";

export default function CodeLookup({ className = "" }) {
  const [code, setCode] = useState("");

  const handleSearch = (e) => {
    e.preventDefault();
    // TODO: wire to API when backend exists
    alert(`Search for "${code}" — not connected yet.`);
  };

  return (
    <div className={`landing-code-lookup ${className}`.trim()}>
      <form className="landing-code-form" onSubmit={handleSearch}>
        <input
          type="search"
          className="landing-code-input"
          placeholder="Enter community or organization code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="Code"
        />
        <button type="submit" className="landing-code-button">
          Search
        </button>
      </form>
      <p className="landing-code-help">
        Codes are provided by your organization or community leader.{" "}
        <Link to="/search-another-way">Search another way</Link>
      </p>
    </div>
  );
}
