import { Link, useSearchParams } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import MessageInbox from "../components/MessageInbox";
import "../styles/Dashboard.css";

export default function PersonalInboxPage() {
  const [params] = useSearchParams();
  const composeDefaults = params.get("to_org")
    ? { to_organization_slug: params.get("to_org") }
    : params.get("to")
      ? { to_username: params.get("to") }
      : null;

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to="/dashboard" className="dashboard-back">
          ← Back to dashboard
        </Link>
        <div className="dashboard-header">
          <h1>Messages</h1>
          <p>
            Your personal inbox, drafts, and messages from people you don&apos;t
            know yet.
          </p>
        </div>
        <div className="dashboard-card">
          <MessageInbox
            apiBase="/api/me/inbox"
            mailboxKind="personal"
            composeDefaults={composeDefaults}
            title="Personal inbox"
          />
        </div>
      </main>
    </div>
  );
}
