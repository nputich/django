import "../styles/Tags.css";

/** Render content body with line breaks and safe auto-linked http(s) URLs. */
function RichBody({ text }) {
  if (!text) return null;
  const parts = [];
  const re = /(https?:\/\/[^\s<]+)/g;
  let last = 0;
  let match;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(<span key={key++}>{text.slice(last, match.index)}</span>);
    }
    const href = match[1].replace(/[.,);]+$/, "");
    const trailing = match[1].slice(href.length);
    parts.push(
      <a key={key++} href={href} target="_blank" rel="noopener noreferrer">
        {href}
      </a>
    );
    if (trailing) parts.push(<span key={key++}>{trailing}</span>);
    last = match.index + match[1].length;
  }
  if (last < text.length) parts.push(<span key={key++}>{text.slice(last)}</span>);
  return <p className="content-block-body" style={{ whiteSpace: "pre-wrap" }}>{parts}</p>;
}

/**
 * Banner / text / video block for meeting content slides and survey content questions.
 */
export default function ContentBlock({ content, title = "" }) {
  if (!content && !title) return null;
  const banner = content?.banner_url;
  const embed = content?.video_embed?.embed_url;
  const body = content?.body || "";

  return (
    <div className="content-block">
      {title ? <h2 className="content-block-title">{title}</h2> : null}
      {banner ? (
        <div className="content-block-banner">
          <img src={banner} alt="" />
        </div>
      ) : null}
      <RichBody text={body} />
      {embed ? (
        <div className="content-block-video">
          <iframe
            title="Video"
            src={embed}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : content?.video_url && !embed ? (
        <p className="dashboard-meta">
          Video link:{" "}
          <a href={content.video_url} target="_blank" rel="noopener noreferrer">
            {content.video_url}
          </a>
          {" "}(use a YouTube or Vimeo link for an in-page player)
        </p>
      ) : null}
    </div>
  );
}
