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
    return "\n".join(pages)


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

            images.append({
                "page": page_idx + 1,
                "filename": filename,
                "width": width,
                "height": height,
                "path": filepath,
            })

    doc.close()
    return images


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

    # Determine season
    if "2025" in name:
        result["season"] = "2025"
    elif "2022-2025" in name or "lookback" in name_lower:
        result["season"] = "special"
    else:
        result["season"] = "2024"

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
