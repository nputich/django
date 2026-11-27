import { Link, Navigate, useLocation } from "react-router-dom";
import ArticleMarkdown from "../components/ArticleMarkdown";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import { getLegalDocumentByPath } from "../legalDocuments";
import "../styles/Landing.css";
import "../styles/KnowledgeCenter.css";
import "../styles/Legal.css";

export default function LegalDocumentPage() {
  const { pathname } = useLocation();
  const document = getLegalDocumentByPath(pathname);

  if (!document) {
    return <Navigate to="/" replace />;
  }

  return (
    <MarketingLayout mainClassName="landing-main legal-page">
      <header className="landing-hero legal-hero">
        <SiteLogo />
        <h1 className="legal-title">{document.title}</h1>
      </header>

      <ArticleMarkdown content={document.content} />

      <p className="legal-related">
        See also{" "}
        <Link to={document.related.path}>{document.related.label}</Link>
      </p>

      <p className="legal-back">
        <Link to="/">← Back to home</Link>
      </p>
    </MarketingLayout>
  );
}
