import { Link } from "react-router-dom";
import AppLayout from "../components/layout/AppLayout";

function NotFound() {
  return (
    <AppLayout>
      <div style={{ textAlign: "center", padding: "48px 20px" }}>
        <h1 style={{ margin: "0 0 8px", fontSize: "2rem" }}>404</h1>
        <p style={{ color: "var(--text-muted)", marginBottom: "24px" }}>
          This page does not exist.
        </p>
        <Link
          to="/"
          style={{ fontWeight: 600, color: "#854d0e" }}
        >
          Back to organization lookup
        </Link>
      </div>
    </AppLayout>
  );
}

export default NotFound;
