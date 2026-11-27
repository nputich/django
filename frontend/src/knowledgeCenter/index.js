import { KNOWLEDGE_CENTER_ARTICLES } from "./articles";

/** List all articles (swap for API fetch later). */
export function listKnowledgeCenterArticles() {
  return KNOWLEDGE_CENTER_ARTICLES;
}

export function getKnowledgeCenterArticleBySlug(urlSlug) {
  if (!urlSlug) return null;
  return (
    KNOWLEDGE_CENTER_ARTICLES.find((article) => article.urlSlug === urlSlug) ??
    null
  );
}

export function getKnowledgeCenterArticleById(id) {
  if (!id) return null;
  return KNOWLEDGE_CENTER_ARTICLES.find((article) => article.id === id) ?? null;
}

/** Case-insensitive hashtag match. Pass null/empty to return all. */
export function filterKnowledgeCenterArticlesByHashtag(hashtag) {
  const articles = listKnowledgeCenterArticles();
  const needle = (hashtag || "").trim().replace(/^#/, "").toLowerCase();
  if (!needle) return articles;
  return articles.filter((article) =>
    (article.hashtags || []).some((tag) => tag.toLowerCase() === needle)
  );
}

export function formatHashtagLabel(tag) {
  const cleaned = String(tag || "").replace(/^#/, "");
  return cleaned ? `#${cleaned}` : "";
}

export function knowledgeCenterArticlePath(article) {
  return `/knowledge-center/${article.urlSlug}`;
}
