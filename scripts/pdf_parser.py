"""Extract text and images from Free Chee PDFs using PyMuPDF."""

import fitz
import os
import re
import hashlib


def extract_text(pdf_path):
    """Extract all text from a PDF, page by page."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return pages


def extract_full_text(pdf_path):
    """Extract all text from a PDF as a single string."""
    pages = extract_text(pdf_path)
    text = "\n".join(pages)

    # A hyphenated compound split across two lines ("flat-\nout") would otherwise
    # become "flat- out" once newlines are flattened to spaces. Only join when a
    # letter follows the break, so numeric splits in tables ("2-\n2") are left alone.
    text = re.sub(r"(?<=[A-Za-z0-9])-\n(?=[A-Za-z])", "-", text)
    return text


def extract_images(pdf_path, output_dir, prefix=""):
    """Extract embedded images from a PDF and save to output_dir.

    Returns list of {page, filename, width, height} dicts.
    """
    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    images = []

    for page_idx, page in enumerate(doc):
        image_list = page.get_images(full=True)
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            if not base_image:
                continue

            image_bytes = base_image["image"]
            ext = base_image["ext"]
            width = base_image["width"]
            height = base_image["height"]

            # Skip tiny images (likely icons/artifacts)
            if width < 50 or height < 50:
                continue

            # Generate deterministic filename from content hash
            img_hash = hashlib.md5(image_bytes).hexdigest()[:8]
            filename = f"{prefix}p{page_idx + 1}_{img_idx + 1}_{img_hash}.{ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            # Vertical position, so callers can tell which section an image
            # falls under when a heading shares its page.
            try:
                rects = page.get_image_rects(xref)
                y = rects[0].y0 if rects else 0.0
            except Exception:
                y = 0.0

            images.append({
                "page": page_idx + 1,
                "y": y,
                "filename": filename,
                "width": width,
                "height": height,
                "path": filepath,
            })

    doc.close()
    return images


def extract_links(pdf_path):
    """Extract external hyperlinks with their anchor text.

    PDF link annotations are separate from the text layer, so extracting text
    alone silently drops every link. Returns a list of
    {uri, text, occurrence} where `occurrence` is the 0-based index of that
    anchor text among all its occurrences in the document, so the caller can
    re-attach the link to the right instance.
    """
    doc = fitz.open(pdf_path)
    page_texts = [page.get_text("text") for page in doc]
    links = []

    for page_idx, page in enumerate(doc):
        for link in page.get_links():
            uri = link.get("uri")
            if not uri:
                continue
            # get_textbox() bleeds in text from neighbouring lines, so collect
            # only words that actually sit inside the link rectangle.
            rect = link["from"]
            inside = []
            for w in page.get_text("words"):
                wr = fitz.Rect(w[:4])
                if wr.get_area() <= 0:
                    continue
                overlap = (wr & rect).get_area() / wr.get_area()
                if overlap > 0.5:
                    inside.append(w[4])
            anchor_text = " ".join(" ".join(inside).split()).strip(" .,;:")
            if not anchor_text:
                continue

            # How many times has this anchor already appeared, in document
            # order? Count matches on earlier pages, plus the part of this page
            # that lies above the link (or to its left on the same line).
            above = fitz.Rect(0, 0, page.rect.x1, rect.y0)
            left_of = fitz.Rect(0, rect.y0, rect.x0, rect.y1)
            preceding = " ".join(page.get_textbox(above).split()) + " " + \
                        " ".join(page.get_textbox(left_of).split())
            # Whole-word matching, so an anchor of "here" does not match
            # inside "there" or "where" (the replacement side matches the same way).
            pat = re.compile(r"\b" + re.escape(anchor_text) + r"\b")
            before = sum(len(pat.findall(" ".join(t.split())))
                         for t in page_texts[:page_idx])
            before += len(pat.findall(preceding))

            links.append({
                "uri": uri,
                "text": anchor_text,
                "occurrence": before,
            })

    doc.close()
    return links


def extract_section_anchors(pdf_path, owners):
    """Locate each owner's section heading as (page, y).

    Headings read "Team Name (Owner)" or, for a one-word team, just the owner,
    optionally numbered. Returns {owner: (page, y)} for those found.
    """
    doc = fitz.open(pdf_path)
    lowered = {o.lower(): o for o in owners}
    out = {}

    for page_no, page in enumerate(doc, start=1):
        for block in page.get_text("blocks"):
            y0, text = block[1], block[4]
            for line in text.splitlines():
                line = line.strip()
                if not line or len(line) > 70:
                    continue
                m = re.match(r"^.*?\(([A-Za-z]+)\)$", line)
                candidate = m.group(1) if m else re.sub(r"^\d+[.)]\s*", "", line)
                owner = lowered.get(candidate.lower())
                if owner and owner not in out:
                    out[owner] = (page_no, y0)

    doc.close()
    return out


def parse_filename(filename):
    """Parse a PDF filename to determine season, week, and type.

    Returns dict with: season, week, type, sort_key
    """
    name = os.path.basename(filename)
    name_lower = name.lower()

    result = {
        "filename": name,
        "season": None,
        "week": None,
        "type": "regular",
        "sort_key": 0,
    }

    # Determine season: lookback is special; otherwise use the 4-digit year in
    # the filename. Early 2024 PDFs have no year in the name, so default to 2024.
    if "2022-2025" in name or "lookback" in name_lower:
        result["season"] = "special"
    else:
        m = re.search(r"20\d{2}", name)
        result["season"] = m.group(0) if m else "2024"

    # Determine week and type
    if "lookback" in name_lower:
        result["type"] = "lookback"
        result["week"] = None
        result["sort_key"] = 9999
    elif "midseason" in name_lower:
        result["type"] = "midseason"
        # Extract week from "Week 8"
        m = re.search(r'week\s*(\d+)', name_lower)
        result["week"] = int(m.group(1)) if m else 8
        result["sort_key"] = result["week"]
    elif "preseason" in name_lower:
        result["type"] = "preseason"
        result["week"] = 0  # Sort before week 1
        result["sort_key"] = 0
    elif "final" in name_lower:
        result["type"] = "final"
        result["week"] = 99  # Sort after all regular weeks
        result["sort_key"] = 99
    elif "playoff" in name_lower and "week" in name_lower:
        result["type"] = "playoff_preview"
        m = re.search(r'week\s*(\d+)', name_lower)
        result["week"] = int(m.group(1)) if m else 15
        result["sort_key"] = result["week"]
    else:
        m = re.search(r'week\s*(\d+)', name_lower)
        if m:
            result["week"] = int(m.group(1))
            result["sort_key"] = result["week"]

    return result


if __name__ == "__main__":
    import sys
    pdf_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    for f in sorted(os.listdir(pdf_dir)):
        if f.endswith(".pdf"):
            info = parse_filename(f)
            print(f"{f}")
            print(f"  Season: {info['season']}, Week: {info['week']}, Type: {info['type']}")
            print()
