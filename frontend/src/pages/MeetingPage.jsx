import { Link, useParams } from "react-router-dom";
import "../styles/Landing.css";
import "../styles/CodeResults.css";

export default function MeetingPage() {
  const { id } = useParams();

  return (
    <div className="resource-page">
      <Link to="/" className="resource-back">
        &larr; Back to home
      </Link>
      <h1>Meeting</h1>
      <p>Meeting #{id} — live Q&amp;A coming in a later phase.</p>
    </div>
  );
}