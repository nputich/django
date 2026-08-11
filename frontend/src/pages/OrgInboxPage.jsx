import { Link, useParams, useSearchParams } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import MessageInbox from "../components/MessageInbox";
import "../styles/Dashboard.css";

export default function OrgInboxPage() {
  const { slug } = useParams();
  const [params] = useSearchParams();
  const composeDefaults = params.get("to")
    ? { to_username: params.get("to") }
    : null;

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to organization
        </Link>
        <div className="dashboard-header">
          <h1>Organization messages</h1>
          <p>
            Same inbox system as personal accounts — primary inbox, unknown
            senders, and drafts.
          </p>
        </div>
        <div className="dashboard-card">
          <MessageInbox
            apiBase={`/api/organizations/${slug}/inbox`}
            mailboxKind="organization"
            composeDefaults={composeDefaults}
            title="Organization inbox"
          />
        </div>
      </main>
    </div>
  );
}
