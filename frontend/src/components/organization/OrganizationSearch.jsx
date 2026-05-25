import "../../styles/OrganizationSearch.css";

function OrganizationSearch({ code, onCodeChange, onSubmit, loading }) {
  return (
    <form className="org-search" onSubmit={onSubmit}>
      <label htmlFor="org-code" className="org-search-label">
        Organization code
      </label>
      <div className="org-search-row">
        <input
          id="org-code"
          type="text"
          className="org-search-input"
          placeholder="Enter your group code"
          value={code}
          onChange={(e) => onCodeChange(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          disabled={loading}
        />
        <button type="submit" className="org-search-btn" disabled={loading}>
          {loading ? "Searching…" : "Find"}
        </button>
      </div>
    </form>
  );
}

export default OrganizationSearch;
