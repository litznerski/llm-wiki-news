#!/usr/bin/env python3
"""
scripts/extract_articles_trafilatura.py
Reads GDELT news feed JSON (produced by fetch_gdelt_bigquery.py), extracts full article text
and metadata using Trafilatura, applies deduplication, and saves Obsidian-native markdown notes to raw/articles/.
"""

import os
import sys
import re
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

VAULT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = VAULT_ROOT / "raw" / "articles"

# Clean filename sanitizer
INVALID_CHARS_RE = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(title: str, max_length: int = 140) -> str:
    """Sanitizes article title for safe cross-platform filesystem filenames while preserving Arabic & Unicode."""
    cleaned = INVALID_CHARS_RE.sub(" ", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned or "untitled_article"


def get_existing_article_sources(articles_dir: Path) -> Tuple[Set[str], Set[str]]:
    """Scans raw/articles/ to extract already-downloaded URLs and normalized titles for deduplication."""
    existing_urls = set()
    existing_titles = set()

    if not articles_dir.exists():
        return existing_urls, existing_titles

    for f in articles_dir.glob("*.md"):
        existing_titles.add(f.stem.strip().lower())
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if line.strip() == "---" and existing_urls:
                        # end of frontmatter
                        break
                    if line.startswith("source:"):
                        val = line.split("source:", 1)[1].strip().strip("'\"")
                        if val:
                            existing_urls.add(val)
        except Exception:
            pass

    return existing_urls, existing_titles


def format_locations_as_wikilinks(loc_str: str) -> List[str]:
    """Converts semicolon-delimited Sudan locations into canonical wikilinks."""
    if not loc_str:
        return []
    parts = [p.strip() for p in loc_str.split(";") if p.strip()]
    seen = set()
    res = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            res.append(f"[[{p}]]")
    return res


def extract_with_trafilatura(url: str, timeout: int = 20) -> Optional[Dict[str, Any]]:
    """Fetches URL and extracts full body text and metadata using Trafilatura."""
    try:
        import trafilatura
    except ImportError:
        print("[!] Error: 'trafilatura' is not installed.", file=sys.stderr)
        print("    Install it via: pip install trafilatura", file=sys.stderr)
        sys.exit(1)

    # Set up polite User-Agent
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None

    # Extract text with precision
    extracted_text = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        url=url,
    )

    if not extracted_text or len(extracted_text.strip()) < 80:
        return None

    # Extract metadata
    metadata = trafilatura.extract_metadata(downloaded)
    title = (metadata.title if metadata and metadata.title else "").strip()
    author = (metadata.author if metadata and metadata.author else "").strip()
    date_str = (metadata.date if metadata and metadata.date else "").strip()
    description = (metadata.description if metadata and metadata.description else "").strip()

    return {
        "text": extracted_text.strip(),
        "title": title,
        "author": author,
        "date": date_str,
        "description": description,
    }


def find_latest_news_json(news_dir: Path) -> Optional[Path]:
    """Finds the most recent GDELT feed JSON file in news_dir."""
    if not news_dir.exists():
        return None
    candidates = list(news_dir.glob("gdelt_sudan_*.json"))
    if not candidates:
        candidates = list(news_dir.glob("*.json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description="Extract full news articles using Trafilatura and save to raw/articles/.")
    parser.add_argument("--input", "-i", help="Path to input GDELT news JSON file (defaults to latest in news/).")
    parser.add_argument("--output-dir", "-o", default=str(ARTICLES_DIR), help="Output directory for articles (default: raw/articles/).")
    parser.add_argument("--max-articles", type=int, default=50, help="Maximum number of articles to download in this batch (default: 50).")
    parser.add_argument("--delay", type=float, default=1.0, help="Polite delay between HTTP requests in seconds (default: 1.0s).")
    parser.add_argument("--dry-run", action="store_true", help="Simulate extraction without fetching or writing files.")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve input JSON
    if args.input:
        in_path = Path(args.input)
    else:
        in_path = find_latest_news_json(VAULT_ROOT / "news")

    if not in_path or not in_path.exists():
        print(f"[!] Error: Input JSON not found. Provide --input or place GDELT JSON in {VAULT_ROOT / 'news'}.", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("  Knowledge Lab :: Trafilatura News Article Extractor")
    print(f"  Input Feed JSON  : {in_path}")
    print(f"  Target Directory : {out_dir}")
    print(f"  Batch Limit      : {args.max_articles} articles")
    print(f"  Execution Mode   : {'DRY-RUN' if args.dry_run else 'LIVE EXTRACTION'}")
    print("=" * 70)

    with open(in_path, "r", encoding="utf-8") as fp:
        feed_data = json.load(fp)

    articles = feed_data.get("articles", [])
    if not articles:
        print("[!] No articles found in input JSON.")
        sys.exit(0)

    # Load existing articles for deduplication
    existing_urls, existing_titles = get_existing_article_sources(out_dir)
    print(f"[*] Loaded {len(existing_urls)} existing URLs and {len(existing_titles)} titles for deduplication sentinel.")

    downloaded_count = 0
    skipped_duplicates = 0
    failed_count = 0

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for idx, item in enumerate(articles, 1):
        if downloaded_count >= args.max_articles:
            print(f"[*] Reached batch limit of {args.max_articles} articles.")
            break

        url = item.get("article_url", "").strip()
        if not url:
            continue

        # Deduplication check
        if url in existing_urls:
            skipped_duplicates += 1
            continue

        publisher = item.get("publisher", "Unknown Outlet")
        tier = item.get("tier", "Unknown Tier")
        topic_focus = item.get("topic_focus", "Security / Conflict")
        tone_score = item.get("tone_score", 0.0)
        locations_raw = item.get("sudan_locations", "")
        pub_date_raw = item.get("published_at", "")

        # Format publication date
        if pub_date_raw:
            try:
                published_date = pub_date_raw[:10]
            except Exception:
                published_date = today_str
        else:
            published_date = today_str

        print(f"[{idx}/{len(articles)}] Fetching: {url} ({publisher})...")

        if args.dry_run:
            print(f"      [Dry-Run] Would extract and save article for {url}")
            downloaded_count += 1
            continue

        # Extract using Trafilatura
        extracted = extract_with_trafilatura(url)
        if not extracted:
            print(f"      [!] Failed to extract clean content (paywalled, 404, or empty): {url}")
            failed_count += 1
            time.sleep(args.delay)
            continue

        # Title resolution
        title = extracted.get("title") or item.get("themes") or "Sudan Conflict Report"
        # If title is in existing titles
        if title.strip().lower() in existing_titles:
            skipped_duplicates += 1
            print(f"      [-] Skipped: Title already exists '{title}'")
            continue

        # Build clean frontmatter
        author_val = extracted.get("author") or publisher
        desc_val = extracted.get("description") or ""
        # Escape quotes in description and title
        clean_title = title.replace('"', '\\"')
        clean_desc = desc_val.replace('"', '\\"')

        loc_wikilinks = format_locations_as_wikilinks(locations_raw)
        loc_yaml = json.dumps(loc_wikilinks) if loc_wikilinks else "[]"

        frontmatter = f"""---
title: "{clean_title}"
source: "{url}"
author:
  - "[[{author_val}]]"
published: {published_date}
created: {today_str}
description: "{clean_desc}"
tags:
  - "clippings"
gdelt_tier: "{tier}"
gdelt_topic_focus: "{topic_focus}"
gdelt_tone: {tone_score}
gdelt_locations: {loc_yaml}
---
"""
        full_content = frontmatter + "\n" + extracted["text"] + "\n"

        filename = sanitize_filename(title) + ".md"
        target_file = out_dir / filename

        # Ensure no filename collision
        collision_idx = 1
        while target_file.exists():
            target_file = out_dir / f"{sanitize_filename(title)}_{collision_idx}.md"
            collision_idx += 1

        with open(target_file, "w", encoding="utf-8") as out_fp:
            out_fp.write(full_content)

        # Update cache
        existing_urls.add(url)
        existing_titles.add(title.strip().lower())
        downloaded_count += 1
        print(f"      [✓] Saved: {target_file.name}")

        time.sleep(args.delay)

    print("")
    print("=================================================================")
    print("  Extraction Complete!")
    print(f"  - Successfully extracted : {downloaded_count}")
    print(f"  - Skipped duplicates     : {skipped_duplicates}")
    print(f"  - Failed / Paywalled     : {failed_count}")
    print(f"  - Destination            : {out_dir}")
    print("=================================================================")


if __name__ == "__main__":
    main()
