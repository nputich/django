"""One-off helper: convert legal docx files to markdown for the site."""
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_style_and_text(p):
    texts = []
    for t in p.iter(W + "t"):
        if t.text:
            texts.append(t.text)
        if t.tail:
            texts.append(t.tail)
    text = "".join(texts).strip()
    pPr = p.find(W + "pPr")
    style = ""
    if pPr is not None:
        pStyle = pPr.find(W + "pStyle")
        if pStyle is not None:
            style = pStyle.get(W + "val", "")
    return style, text


def normalize(text):
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufffd": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def docx_to_md(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    blocks = []
    for p in root.iter(W + "p"):
        style, text = para_style_and_text(p)
        text = normalize(text)
        if not text:
            continue
        if style == "Title":
            continue
        if style == "Heading1":
            blocks.append("## " + text)
            continue
        if style == "Heading2":
            blocks.append("### " + text)
            continue
        if style == "Heading3":
            blocks.append("#### " + text)
            continue
        blocks.append(text)
    return "\n\n".join(blocks)


def main():
    out_dir = Path(__file__).resolve().parents[1] / "src" / "content" / "legal"
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [
        (
            Path(r"c:\Users\nputi\Downloads\Last Review for CommuniBetter_Privacy_Policy_Final.docx"),
            "privacy-policy.md",
        ),
        (
            Path(r"c:\Users\nputi\Downloads\FInal_CommuniBetter_Terms_of_Service.docx"),
            "terms-of-service.md",
        ),
    ]
    for src, name in pairs:
        if not src.is_file():
            print(f"Missing: {src}", file=sys.stderr)
            sys.exit(1)
        md = docx_to_md(src)
        (out_dir / name).write_text(md, encoding="utf-8")
        print(f"Wrote {name} ({len(md)} chars)")


if __name__ == "__main__":
    main()
