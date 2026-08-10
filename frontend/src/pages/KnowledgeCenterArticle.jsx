import { Link, Navigate, useParams } from "react-router-dom";
import ArticleMarkdown from "../components/ArticleMarkdown";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import {
  formatHashtagLabel,
  getKnowledgeCenterArticleBySlug,
} from "../knowledgeCenter";
import "../styles/Landing.css";
import "../styles/KnowledgeCenter.css";

/** Prefer the title field for the page heading; drop a matching leading markdown H1. */
function bodyWithoutLeadingTitle(content, title) {
  const text = String(content || "").replace(/^\uFEFF/, "");
  const match = text.match(/^#\s+(.+?)\s*(?:\n|$)/);
  if (match && match[1].trim() === String(title || "").trim()) {
    return text.slice(match[0].length).replace(/^\n+/, "");
  }
  return text;
}

export default function KnowledgeCenterArticle() {
  const { urlSlug } = useParams();
  const article = getKnowledgeCenterArticleBySlug(urlSlug);

  if (!article) {
    return <Navigate to="/knowledge-center" replace />;
  }

  return (
    <MarketingLayout mainClassName="landing-main kc-page kc-page--article">
      <header className="landing-hero kc-hero kc-hero--article">
        <SiteLogo />
        <h1 className="kc-title">{article.title}</h1>
        {(article.hashtags || []).length > 0 && (
          <div className="kc-hashtags kc-hashtags--article" aria-label="Hashtags">
            {article.hashtags.map((tag) => (
              <Link
                key={tag}
                to={`/knowledge-center?tag=${encodeURIComponent(tag)}`}
                className="kc-hashtag"
              >
                {formatHashtagLabel(tag)}
              </Link>
            ))}
          </div>
        )}
      </header>

      <ArticleMarkdown
        content={bodyWithoutLeadingTitle(article.content, article.title)}
      />

      <p className="kc-back">
        <Link to="/knowledge-center">← Back to Knowledge Center</Link>
      </p>
    </MarketingLayout>
  );
}
