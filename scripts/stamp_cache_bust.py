"""Cache-bust local CSS/JS by stamping ?v=<content-hash> on every reference.

Browsers cache GitHub Pages assets aggressively; a content hash makes them
refetch a file only when its contents actually change. Idempotent: strips any
existing ?v= first, then re-stamps from the current file. Run before committing
a deploy. Touches both docs/ and site/; external CDN/font links are ignored.
"""
import re, os, glob, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# href/src -> optional path prefix -> css/ or js/ file -> optional old ?v=
ASSET_RE = re.compile(
    r'(href|src)="((?:[^"]*/)?)((?:css|js)/[A-Za-z0-9_.-]+\.(?:css|js))(?:\?v=[a-f0-9]+)?"'
)


DATA_V_RE = re.compile(r"(const DATA_V = ')[^']*(')")


def stamp_data_version(root):
    """Rewrite DATA_V in js/data-loader.js from a hash of everything in data/."""
    loader = os.path.join(root, "js", "data-loader.js")
    data_dir = os.path.join(root, "data")
    if not (os.path.exists(loader) and os.path.isdir(data_dir)):
        return None
    digest = hashlib.md5()
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if os.path.isfile(path):
            digest.update(name.encode())
            with open(path, "rb") as f:
                digest.update(f.read())
    stamp = digest.hexdigest()[:10]
    src = open(loader, encoding="utf-8").read()
    new = DATA_V_RE.sub(lambda m: f"{m.group(1)}{stamp}{m.group(2)}", src)
    if new != src:
        open(loader, "w", encoding="utf-8").write(new)
    return stamp


def stamp_tree(root):
    hashes = {}

    def h(rel):
        if rel not in hashes:
            with open(os.path.join(root, rel), "rb") as f:
                hashes[rel] = hashlib.md5(f.read()).hexdigest()[:10]
        return hashes[rel]

    changed = 0
    for path in glob.glob(os.path.join(root, "*.html")):
        html = open(path, encoding="utf-8").read()

        def repl(m):
            attr, prefix, rel = m.group(1), m.group(2), m.group(3)
            return f'{attr}="{prefix}{rel}?v={h(rel)}"'

        new = ASSET_RE.sub(repl, html)
        if new != html:
            open(path, "w", encoding="utf-8").write(new)
            changed += 1
    return changed


if __name__ == "__main__":
    for tree in ("docs", "site"):
        v = stamp_data_version(os.path.join(ROOT, tree))
        if v:
            print(f"{tree}: data version {v}")
        n = stamp_tree(os.path.join(ROOT, tree))
        print(f"{tree}: stamped {n} html files")
