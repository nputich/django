import { Link, useSearchParams } from "react-router-dom";
import MarketingLayout from "../components/MarketingLayout";
import SiteLogo from "../components/SiteLogo";
import {
  filterKnowledgeCenterArticlesByHashtag,
  formatHashtagLabel,
  knowledgeCenterArticlePath,
} from "../knowledgeCenter";
import "../styles/Landing.css";
import "../styles/KnowledgeCenter.css";

export default function KnowledgeCenter() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTag = searchParams.get("tag") || "";
  const articles = filterKnowledgeCenterArticlesByHashtag(activeTag);

  const selectTag = (tag) => {
    const next = new URLSearchParams(searchParams);
    if (!tag) {
      next.delete("tag");
    } else {
      next.set("tag", tag);
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <MarketingLayout mainClassName="landing-main kc-page">
      <header className="landing-hero kc-hero">
        <SiteLogo />
        <h1 className="kc-title">Knowledge Center</h1>
        <p className="kc-lead">
          Guides and practical resources for community organizations.
        </p>
      </header>

      {activeTag && (
        <div className="kc-filter-bar">
          <span className="kc-filter-label">
            Filtered by {formatHashtagLabel(activeTag)}
          </span>
          <button
            type="button"
            className="kc-filter-clear"
            onClick={() => selectTag("")}
          >
            Clear filter
          </button>
        </div>
      )}

      {articles.length === 0 ? (
        <p className="kc-empty">No articles match this hashtag.</p>
      ) : (
        <ul className="kc-article-list">
          {articles.map((article) => (
            <li key={article.id} className="kc-article-card">
              <Link
                to={knowledgeCenterArticlePath(article)}
                className="kc-article-card-main"
              >
                <h2 className="kc-article-card-title">{article.title}</h2>
                <p className="kc-article-card-blurb">{article.blurb}</p>
                <span className="kc-article-card-read">Read Article</span>
              </Link>
              {(article.hashtags || []).length > 0 && (
                <div className="kc-hashtags" aria-label="Hashtags">
                  {article.hashtags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className={
                        activeTag.toLowerCase() === tag.toLowerCase()
                          ? "kc-hashtag kc-hashtag--active"
                          : "kc-hashtag"
                      }
                      onClick={() => selectTag(tag)}
                    >
                      {formatHashtagLabel(tag)}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </MarketingLayout>
  );
}
