"""Generate per-owner shareable career pages + custom Open Graph preview images.

Each owner gets:
  - images/og-career-<slug>.png : a 1200x630 share card (name, record, rings, ppg)
  - career-<slug>.html          : a static page with owner-specific OG meta tags
Outputs to both docs/ and site/. Run after build_engagement_data.py.
"""
import json, os, re
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://mpg000f.github.io/free-chee-rankings/"

BG = (15, 17, 24)
SURFACE = (26, 29, 46)
GOLD = (245, 166, 35)
TEXT = (232, 230, 227)
DIM = (155, 152, 160)

IMPACT = "/mnt/c/Windows/Fonts/impact.ttf"
ARIALBD = "/mnt/c/Windows/Fonts/arialbd.ttf"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
HEAD = IMPACT if os.path.exists(IMPACT) else DEJAVU
BODY = ARIALBD if os.path.exists(ARIALBD) else DEJAVU


def slug(owner):
    return re.sub(r"[^a-z0-9]+", "-", owner.lower())


def font(path, size):
    return ImageFont.truetype(path, size)


def centered(draw, cx, y, text, fnt, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (r - l) / 2 - l, y), text, font=fnt, fill=fill)


def make_card(c, out_path):
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GOLD)
    d.rectangle([0, H - 10, W, H], fill=GOLD)

    centered(d, W // 2, 70, "FREE CHEE CAREER", font(BODY, 34), DIM)
    centered(d, W // 2, 120, c["owner"].upper(), font(HEAD, 130), GOLD)

    # rings (no emoji — PIL fonts lack the trophy glyph)
    rings = c["championships"]
    if rings:
        ring_text, ring_color = f"{rings}-TIME CHAMPION", GOLD
    else:
        ring_text, ring_color = "STILL CHASING THE RING", DIM
    centered(d, W // 2, 290, ring_text, font(BODY, 44), ring_color)

    # stat line
    rec = f"{c['wins']}-{c['losses']}" + (f"-{c['ties']}" if c['ties'] else "")
    centered(d, W // 2, 380, f"{rec}  all-time", font(HEAD, 66), TEXT)

    parts = [f"{c['ppg']} PPG"]
    if c.get("power_score") is not None:
        parts.append(f"Power Score {c['power_score']}")
    if c.get("best_finish"):
        parts.append(f"Best #{c['best_finish']}")
    centered(d, W // 2, 480, "   •   ".join(parts), font(BODY, 36), DIM)

    img.save(out_path, "PNG")


def page_html(c):
    o = c["owner"]
    s = slug(o)
    rec = f"{c['wins']}-{c['losses']}" + (f"-{c['ties']}" if c['ties'] else "")
    bits = [f"{rec} all-time"]
    if c["championships"]:
        bits.append(f"{c['championships']}× champion")
    bits.append(f"{c['ppg']} PPG")
    desc = o + " — " + " • ".join(bits) + ". Free Chee career profile."
    img = f"{BASE_URL}images/og-career-{s}.png"
    url = f"{BASE_URL}career-{s}.html"
    title = f"{o} — Free Chee Career"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <link rel="icon" type="image/png" href="favicon.png">
  <link rel="apple-touch-icon" href="apple-touch-icon.png">
  <meta name="theme-color" content="#0f1118">
  <meta property="og:type" content="profile">
  <meta property="og:site_name" content="Free Chee Headquarters">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{img}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{img}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Oswald:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/style.css">
  <link rel="stylesheet" href="css/animations.css">
</head>
<body>
  <nav class="navbar">
    <div class="navbar-inner">
      <a href="index.html" class="nav-brand">Free Chee</a>
      <div class="nav-links">
        <a href="index.html">Home</a>
        <a href="rankings.html">Rankings</a>
        <a href="stats.html">Stats</a>
        <a href="lookback.html">Lookback</a>
        <a href="rosters.html">Rosters</a>
        <a href="draft-value.html">Draft Value</a>
        <a href="head2head.html">Head-to-Head</a>
        <a href="records.html">Records</a>
        <a href="careers.html" class="active">Careers</a>
      </div>
    </div>
  </nav>

  <div class="page-container">
    <div id="career-content"><p class="placeholder-text">Loading {o}...</p></div>
  </div>

  <footer class="footer">
    <p>Free Chee Headquarters &copy; 2024-2025 &bull; The Committee</p>
  </footer>

  <script>window.CAREER_OWNER = {json.dumps(o)};</script>
  <script src="js/data-loader.js"></script>
  <script src="js/career-render.js"></script>
  <script src="js/career-page.js"></script>
</body>
</html>
"""


def main():
    careers = json.load(open(os.path.join(ROOT, "docs", "data", "careers.json"), encoding="utf-8"))["careers"]
    for root in ("docs", "site"):
        img_dir = os.path.join(ROOT, root, "images")
        for owner, c in careers.items():
            s = slug(owner)
            make_card(c, os.path.join(img_dir, f"og-career-{s}.png"))
            with open(os.path.join(ROOT, root, f"career-{s}.html"), "w", encoding="utf-8") as f:
                f.write(page_html(c))
    print(f"generated {len(careers)} owner pages + cards in docs/ and site/")
    for owner in careers:
        print("  career-%s.html  +  images/og-career-%s.png" % (slug(owner), slug(owner)))


if __name__ == "__main__":
    main()
