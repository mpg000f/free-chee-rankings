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
        n = stamp_tree(os.path.join(ROOT, tree))
        print(f"{tree}: stamped {n} html files")
