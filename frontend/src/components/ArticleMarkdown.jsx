import { Fragment } from "react";

function renderInline(text, keyPrefix) {
  const parts = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match;
  let i = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(
        <Fragment key={`${keyPrefix}-t-${i}`}>
          {text.slice(last, match.index)}
        </Fragment>
      );
    }
    parts.push(<strong key={`${keyPrefix}-b-${i}`}>{match[1]}</strong>);
    last = match.index + match[0].length;
    i += 1;
  }
  if (last < text.length) {
    parts.push(
      <Fragment key={`${keyPrefix}-t-end`}>{text.slice(last)}</Fragment>
    );
  }
  return parts.length ? parts : text;
}

/**
 * Lightweight markdown renderer for Knowledge Center article bodies.
 * Supports: # / ## headings, paragraphs, **bold**, * bullets, numbered lists.
 */
export default function ArticleMarkdown({ content }) {
  const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("# ")) {
      blocks.push(
        <h1 key={`h1-${i}`}>{renderInline(trimmed.slice(2), `h1-${i}`)}</h1>
      );
      i += 1;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      blocks.push(
        <h2 key={`h2-${i}`}>{renderInline(trimmed.slice(3), `h2-${i}`)}</h2>
      );
      i += 1;
      continue;
    }

    if (/^\* /.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\* /.test(lines[i].trim())) {
        const itemText = lines[i].trim().slice(2);
        items.push(
          <li key={`ul-${i}`}>{renderInline(itemText, `ul-${i}`)}</li>
        );
        i += 1;
      }
      blocks.push(<ul key={`ul-block-${i}`}>{items}</ul>);
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const items = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trim())) {
        const itemText = lines[i].trim().replace(/^\d+\.\s/, "");
        items.push(
          <li key={`ol-${i}`}>{renderInline(itemText, `ol-${i}`)}</li>
        );
        i += 1;
      }
      blocks.push(<ol key={`ol-block-${i}`}>{items}</ol>);
      continue;
    }

    const paraLines = [trimmed];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("# ") &&
      !lines[i].trim().startsWith("## ") &&
      !/^\* /.test(lines[i].trim()) &&
      !/^\d+\.\s/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i].trim());
      i += 1;
    }
    const para = paraLines.join(" ");
    blocks.push(
      <p key={`p-${i}`}>{renderInline(para, `p-${i}`)}</p>
    );
  }

  return <div className="kc-article-body">{blocks}</div>;
}
