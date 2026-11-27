import "../styles/HostResults.css";

export default function ResultsBarChart({ bars, compact = false }) {
  if (!bars?.length) {
    return <p className="dashboard-meta host-results-empty">No responses yet.</p>;
  }

  return (
    <div
      className={`host-bar-chart${compact ? " host-bar-chart--compact" : ""}`}
      aria-label="Results chart"
    >
      {bars.map((bar) => (
        <div key={bar.label} className="host-bar-row">
          <span className="host-bar-label" title={bar.label}>
            {bar.label}
          </span>
          <div className="host-bar-track">
            <div className="host-bar-fill" style={{ width: `${bar.percent}%` }} />
          </div>
          <span className="host-bar-count">{bar.count}</span>
        </div>
      ))}
    </div>
  );
}
