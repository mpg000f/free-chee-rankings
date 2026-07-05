"""One-command site build. Run after adding a new week's PDF.

Pipeline:
  1. generate_site_data.py   parse all root PDFs -> site/data + site/images
  2. sync site/{data,images} -> docs/{data,images}   (docs/ is what Pages serves)
  3. build_engagement_data.py  rebuild Head-to-Head / Records / Player Profiles data
  4. build_owner_share_pages.py  rebuild per-owner share pages + preview cards
  5. stamp_cache_bust.py       re-stamp ?v=<hash> on css/js so browsers refetch

Usage:  python3 scripts/build.py
Then:   git add -A && git commit && git push
"""
import os, sys, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")


def run(script):
    print(f"\n=== {script} ===")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)],
                       cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"BUILD FAILED at {script} (exit {r.returncode})")


def sync(subdir):
    src = os.path.join(ROOT, "site", subdir)
    dst = os.path.join(ROOT, "docs", subdir)
    os.makedirs(dst, exist_ok=True)
    n = 0
    for name in os.listdir(src):
        s = os.path.join(src, name)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, name))
            n += 1
    print(f"  synced {n} files: site/{subdir} -> docs/{subdir}")


def main():
    run("generate_site_data.py")
    print("\n=== sync site -> docs ===")
    sync("data")
    sync("images")
    run("build_engagement_data.py")
    run("build_power_ratings.py")
    run("build_owner_share_pages.py")
    run("stamp_cache_bust.py")
    print("\nBuild complete. Review with `git status`, then commit and push.")


if __name__ == "__main__":
    main()
