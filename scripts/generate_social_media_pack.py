"""
Generate CommuniBetter social / YouTube media pack (PNG) from repo assets.
Requires: Node (npx @resvg/resvg-js-cli), Pillow.
"""
from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ASSETS = FRONTEND / "src" / "assets"
PUBLIC = FRONTEND / "public"
SVG_LOGO = ASSETS / "logo-communibetter.svg"
SVG_TAGLINE = ASSETS / "logo-communibetter-tagline.svg"
OUT = Path.home() / "Downloads" / "CommuniBetter-Social-Media-Pack"

BRAND_BLUE = (39, 102, 144)
BRAND_INK = (21, 21, 21)
BRAND_MUTED = (63, 74, 85)
BG_TOP = (248, 249, 247)
BG_BOTTOM = (236, 240, 237)


def run_resvg(svg: Path, out_png: Path, width: int) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = (
        f'npx --yes @resvg/resvg-js-cli --fit-width={width} '
        f'--font-dir "C:/Windows/Fonts" --background "rgba(0,0,0,0)" '
        f'"{svg}" "{out_png}"'
    )
    subprocess.run(cmd, cwd=FRONTEND, check=True, shell=True)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def vertical_gradient(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def paste_centered(base: Image.Image, overlay: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    max_w, max_h = x1 - x0, y1 - y0
    ow, oh = overlay.size
    scale = min(max_w / ow, max_h / oh, 1.0)
    if scale < 1.0:
        overlay = overlay.resize(
            (int(ow * scale), int(oh * scale)), Image.Resampling.LANCZOS
        )
    ow, oh = overlay.size
    x = x0 + (max_w - ow) // 2
    y = y0 + (max_h - oh) // 2
    if overlay.mode == "RGBA":
        base.paste(overlay, (x, y), overlay)
    else:
        base.paste(overlay, (x, y))


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.mode == "RGBA":
        img.save(path, "PNG", optimize=True)
    else:
        img.convert("RGB").save(path, "PNG", optimize=True)


def dilate_alpha(alpha: Image.Image, radius: int) -> Image.Image:
    expanded = alpha
    for _ in range(max(radius, 1)):
        expanded = expanded.filter(ImageFilter.MaxFilter(3))
    return expanded


def white_outline_layer(
    img: Image.Image, stroke: int = 4, color: tuple[int, int, int, int] = (255, 255, 255, 255)
) -> Image.Image:
    """White halo behind non-transparent pixels (readable on dark video)."""
    rgba = img.convert("RGBA")
    alpha = rgba.split()[3]
    expanded = dilate_alpha(alpha, stroke)
    ring = ImageChops.subtract(expanded, alpha)
    outline = Image.new("RGBA", rgba.size, color)
    outline.putalpha(ring)
    return Image.alpha_composite(outline, rgba)


def soften(img: Image.Image, opacity: float = 0.9) -> Image.Image:
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    a = a.point(lambda p: int(p * opacity))
    return Image.merge("RGBA", (r, g, b, a))


def fit_watermark(source: Image.Image, size: int, stroke: int, opacity: float) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    src = source.convert("RGBA")
    ow, oh = src.size
    scale = (size * 0.88) / max(ow, oh)
    src = src.resize((int(ow * scale), int(oh * scale)), Image.Resampling.LANCZOS)
    marked = white_outline_layer(soften(src, opacity), stroke=stroke)
    paste_centered(canvas, marked, (0, 0, size, size))
    return canvas


def render_masters(tmp: Path) -> tuple[Path, Path]:
    logo_png = tmp / "logo.png"
    tagline_png = tmp / "tagline.png"
    run_resvg(SVG_LOGO, logo_png, width=1400)
    run_resvg(SVG_TAGLINE, tagline_png, width=1800)
    return logo_png, tagline_png


def build_profile(logo: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    pad = int(size * 0.12)
    paste_centered(canvas, logo.convert("RGBA"), (pad, pad, size - pad, size - pad))
    return canvas


def build_profile_from_icon(icon: Image.Image, size: int) -> Image.Image:
    """Square app-icon style (blue mark on white) — good when cropped to a circle."""
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    pad = int(size * 0.08)
    paste_centered(canvas, icon.convert("RGBA"), (pad, pad, size - pad, size - pad))
    return canvas


def build_banner(
    tagline: Image.Image, width: int, height: int, safe: tuple[int, int, int, int]
) -> Image.Image:
    canvas = vertical_gradient((width, height)).convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    sx0, sy0, sx1, sy1 = safe
    draw.rounded_rectangle(
        [sx0, sy0, sx1, sy1],
        radius=24,
        fill=(255, 255, 255, 235),
        outline=(39, 102, 144, 40),
        width=2,
    )
    paste_centered(canvas, tagline.convert("RGBA"), (sx0 + 40, sy0 + 30, sx1 - 40, sy1 - 30))
    return canvas


def build_thumbnail(tagline: Image.Image, logo: Image.Image) -> Image.Image:
    w, h = 1280, 720
    canvas = vertical_gradient((w, h)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, w, 8], fill=BRAND_BLUE)
    paste_centered(canvas, tagline.convert("RGBA"), (80, 140, w - 80, h - 80))
    small = logo.copy()
    sw = int(w * 0.22)
    sh = int(sw * logo.height / logo.width)
    small = small.resize((sw, sh), Image.Resampling.LANCZOS)
    canvas.paste(small.convert("RGBA"), (56, 56), small.convert("RGBA"))
    return canvas


def build_story(tagline: Image.Image) -> Image.Image:
    w, h = 1080, 1920
    canvas = vertical_gradient((w, h)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([540 - 420, 200, 540 + 420, 1040], fill=(39, 102, 144, 18))
    paste_centered(canvas, tagline.convert("RGBA"), (80, 620, w - 80, 1320))
    font = load_font(42)
    tag = "Build better communities."
    tw = draw.textlength(tag, font=font)
    draw.text(((w - tw) / 2, 1380), tag, fill=BRAND_MUTED, font=font)
    return canvas


def build_og(tagline: Image.Image) -> Image.Image:
    w, h = 1200, 630
    canvas = vertical_gradient((w, h)).convert("RGBA")
    paste_centered(canvas, tagline.convert("RGBA"), (60, 80, w - 60, h - 60))
    return canvas


def build_square(tagline: Image.Image, size: int = 1080) -> Image.Image:
    canvas = vertical_gradient((size, size)).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, size, 6], fill=BRAND_BLUE)
    paste_centered(canvas, tagline.convert("RGBA"), (72, 220, size - 72, size - 120))
    return canvas


def write_readme() -> None:
    text = textwrap.dedent(
        """
        CommuniBetter — Social & YouTube media pack
        Tagline: Build better communities.

        Upload each PNG to the place shown in the filename (folder + numbered name).

        ── YOUTUBE (Studio → Customization) ──
        youtube/01-youtube-channel-profile-picture-800x800.png
          → Branding → Profile picture (full wordmark on white)

        youtube/01b-youtube-channel-profile-picture-brand-mark-800x800.png
          → Optional profile picture (blue “Better” arrow mark — same as site favicon)

        youtube/02-youtube-channel-banner-art-2560x1440.png
          → Branding → Banner image

        youtube/03-youtube-video-thumbnail-template-1280x720.png
          → Per video → Upload thumbnail

        youtube/04-youtube-video-watermark-wordmark-white-outline-200px.png
          → Branding → Video watermark (full logo + white outline for dark scenes)

        youtube/05-youtube-video-watermark-brand-mark-white-outline-200px-RECOMMENDED.png
          → Branding → Video watermark (small favicon-style mark — usually best at corner size)

        ── BRAND MARK / FAVICON (site icon — blue arrow from “Better”) ──
        brand-mark/01-website-favicon-512x512.png
          → Source for browser tab icon (matches communibetter.com)

        brand-mark/02-apple-touch-icon-180x180.png
          → iOS “Add to Home Screen” / some platforms’ app icon slot

        brand-mark/03-brand-mark-transparent-outline-for-dark-backgrounds-512.png
          → Reference: isolated mark with white outline (overlays, slides, dark video)

        (Also copied: favicon-16/32/48/64 and favicon.ico from the live site.)

        ── FACEBOOK / INSTAGRAM / LINKEDIN / X / GENERAL ──
        See subfolders — filenames describe destination (profile, cover, story, og:image).

        ── MASTER FILES ──
        00-master-files/ — Logo.ai, Logo.eps, SVG wordmarks (do not upload as social images).

        Regenerate after logo changes:
          python scripts/generate_social_media_pack.py
        """
    ).strip()
    (OUT / "00-README-WHERE-TO-UPLOAD.txt").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    if not SVG_LOGO.is_file() or not SVG_TAGLINE.is_file():
        raise SystemExit("Missing SVG assets in frontend/src/assets/")

    tmp = OUT / "_render_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)

    logo_path, tagline_path = render_masters(tmp)
    logo = Image.open(logo_path)
    tagline = Image.open(tagline_path)

    icon_path = PUBLIC / "apple-touch-icon.png"
    if not icon_path.is_file():
        icon_path = PUBLIC / "favicon-64x64.png"
    icon = Image.open(icon_path)

    masters = OUT / "00-master-files"
    masters.mkdir(exist_ok=True)
    for src in (SVG_LOGO, SVG_TAGLINE):
        shutil.copy2(src, masters / src.name)
    for src in (
        Path.home() / "Downloads" / "Logo.ai",
        Path.home() / "Downloads" / "Logo.eps",
    ):
        if src.is_file():
            shutil.copy2(src, masters / src.name)

    yt = OUT / "youtube"
    save_png(build_profile(logo, 800), yt / "01-youtube-channel-profile-picture-800x800.png")
    save_png(
        build_profile_from_icon(icon, 800),
        yt / "01b-youtube-channel-profile-picture-brand-mark-800x800.png",
    )
    save_png(
        build_banner(tagline, 2560, 1440, (507, 509, 2053, 932)),
        yt / "02-youtube-channel-banner-art-2560x1440.png",
    )
    save_png(
        build_thumbnail(tagline, logo),
        yt / "03-youtube-video-thumbnail-template-1280x720.png",
    )
    save_png(
        fit_watermark(logo, 200, stroke=5, opacity=0.92),
        yt / "04-youtube-video-watermark-wordmark-white-outline-200px.png",
    )
    save_png(
        fit_watermark(icon, 200, stroke=4, opacity=0.95),
        yt / "05-youtube-video-watermark-brand-mark-white-outline-200px-RECOMMENDED.png",
    )
    # YouTube accepts upload; they scale down — also save 150 for convenience
    save_png(
        fit_watermark(icon, 150, stroke=3, opacity=0.95),
        yt / "05-youtube-video-watermark-brand-mark-white-outline-150px-RECOMMENDED.png",
    )

    mark = OUT / "brand-mark"
    mark.mkdir(parents=True, exist_ok=True)
    for name in (
        "favicon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon-48x48.png",
        "favicon-64x64.png",
        "favicon.ico",
        "apple-touch-icon.png",
    ):
        src = PUBLIC / name
        if src.is_file():
            shutil.copy2(src, mark / name)
    fav512 = PUBLIC / "favicon.png"
    if fav512.is_file():
        im = Image.open(fav512).convert("RGBA")
        im = im.resize((512, 512), Image.Resampling.LANCZOS)
        save_png(im, mark / "01-website-favicon-512x512.png")
    if icon_path.is_file():
        save_png(
            Image.open(icon_path),
            mark / "02-apple-touch-icon-180x180.png",
        )
    # Large mark with outline (matches the blue arrow glyph you use beside the wordmark)
    mark_large = icon.resize((512, 512), Image.Resampling.LANCZOS)
    save_png(
        fit_watermark(mark_large, 512, stroke=8, opacity=1.0),
        mark / "03-brand-mark-transparent-outline-for-dark-backgrounds-512.png",
    )

    fb = OUT / "facebook"
    save_png(build_profile(logo, 320), fb / "01-facebook-page-profile-picture-320x320.png")
    save_png(
        build_profile_from_icon(icon, 320),
        fb / "01b-facebook-page-profile-picture-brand-mark-320x320.png",
    )
    save_png(
        build_banner(tagline, 820, 312, (40, 40, 780, 272)),
        fb / "02-facebook-page-cover-photo-820x312.png",
    )

    ig = OUT / "instagram"
    save_png(build_profile(logo, 320), ig / "01-instagram-profile-picture-320x320.png")
    save_png(
        build_profile_from_icon(icon, 320),
        ig / "01b-instagram-profile-picture-brand-mark-320x320.png",
    )
    save_png(build_square(tagline), ig / "02-instagram-square-post-template-1080x1080.png")
    save_png(build_story(tagline), ig / "03-instagram-story-template-1080x1920.png")

    li = OUT / "linkedin"
    save_png(build_profile(logo, 400), li / "01-linkedin-company-page-logo-400x400.png")
    save_png(
        build_profile_from_icon(icon, 400),
        li / "01b-linkedin-company-page-logo-brand-mark-400x400.png",
    )
    save_png(
        build_banner(tagline, 1584, 396, (80, 60, 1504, 336)),
        li / "02-linkedin-company-cover-image-1584x396.png",
    )

    xdir = OUT / "x-twitter"
    save_png(build_profile(logo, 400), xdir / "01-x-profile-picture-400x400.png")
    save_png(
        build_profile_from_icon(icon, 400),
        xdir / "01b-x-profile-picture-brand-mark-400x400.png",
    )
    save_png(
        build_banner(tagline, 1500, 500, (120, 80, 1380, 420)),
        xdir / "02-x-header-image-1500x500.png",
    )

    gen = OUT / "general"
    save_png(build_og(tagline), gen / "01-open-graph-link-preview-1200x630.png")
    save_png(build_profile(logo, 512), gen / "02-square-brand-mark-512x512.png")
    save_png(
        build_profile_from_icon(icon, 512),
        gen / "02b-square-app-icon-brand-mark-512x512.png",
    )

    write_readme()
    shutil.rmtree(tmp)
    print(f"Wrote media pack to: {OUT}")


if __name__ == "__main__":
    main()
