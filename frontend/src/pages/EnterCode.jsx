import { useState } from "react";
import { Link } from "react-router-dom";
import logo from "../assets/logo-full.png";
import "../styles/Landing.css";
import "../styles/EnterCode.css";
export default function EnterCode() {
  const [code, setCode] = useState("");
  const handleSearch = (e) => {
    e.preventDefault();
    // TODO: wire to API when backend exists
    // e.g. api.get(`/api/codes/${code}/`)
    alert(`Search for "${code}" — not connected yet.`);
  };
  return (
    <div className="enter-code">
      <Link to="/" className="enter-code-back">← Back</Link>
      <img src={logo} alt="communiB" className="enter-code-logo" />
      <h1>Enter a code</h1>
      <p className="enter-code-subtitle">
        Enter your community or organization code below.
      </p>
      <form className="enter-code-form" onSubmit={handleSearch}>
        <input
          type="search"
          className="enter-code-input"
          placeholder="Enter code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-label="Code"
        />
        <button type="submit" className="enter-code-button">
          Search
        </button>
      </form>
      <p className="enter-code-help">
        Codes are provided by your organization or community leader.
      </p>
      <p className="enter-code-alt">
        <Link to="/search-another-way">Search another way</Link>
      </p>
    </div>
  );
}
