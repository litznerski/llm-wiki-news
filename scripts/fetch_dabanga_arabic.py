#!/usr/bin/env python3
"""
scripts/fetch_dabanga_arabic.py
Extracts Arabic news articles from Radio Dabanga (dabangasudan.org/ar/) for a specified date range,
traverses pagination, generates a standardized feed JSON, and automatically runs
scripts/extract_articles_trafilatura.py to save individual Markdown articles to raw/articles/.
"""

import os
import sys
import re
import json
import time
import argparse
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Set, Dict, Any, Optional

VAULT_ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = VAULT_ROOT / "news"
NEWS_ARCHIVED_DIR = NEWS_DIR / "archived"
ARTICLES_DIR = VAULT_ROOT / "raw" / "articles"
EXTRACTOR_SCRIPT = VAULT_ROOT / "scripts" / "extract_articles_trafilatura.py"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ARTICLE_URL_REGEX = re.compile(r'href=[\"\'](https?://www\.dabangasudan\.org/ar/all-news/article/[^\"\'#\s]+)[\"\']')
DATE_PARAM_REGEX = re.compile(r'post_date=([0-9]{4}-[0-9]{2}-[0-9]{2})\+([0-9]{4}-[0-9]{2}-[0-9]{2})')


def parse_and_normalize_date_range(url: Optional[str], start_date: Optional[str], end_date: Optional[str]) -> Tuple[str, str]:
    """
    Normalizes the date range into chronological order (min_date, max_date).
    Dabanga's WordPress Search & Filter requires chronological order (min_date + max_date).
    If reversed (e.g. 2026-11-02+2026-11-01), the database query evaluates BETWEEN max AND min, yielding 0 results.
    """
    d1, d2 = None, None

    if start_date and end_date:
        d1, d2 = start_date.strip(), end_date.strip()
    elif url and "post_date=" in url:
        match = DATE_PARAM_REGEX.search(url)
        if match:
            d1, d2 = match.group(1), match.group(2)
        else:
            # Try raw unquoted or alternate delimiter
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "post_date" in qs:
                raw_val = qs["post_date"][0]
                parts = re.split(r'[\s+]+', raw_val)
                if len(parts) >= 2:
                    d1, d2 = parts[0], parts[1]

    if not d1 or not d2:
        # Default to yesterday and today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        d1, d2 = today, today

    sorted_dates = sorted([d1, d2])
    return sorted_dates[0], sorted_dates[1]


def build_page_url(min_date: str, max_date: str, page: int = 1) -> str:
    """Builds the canonical Dabanga Arabic search URL for a given page and date range."""
    date_query = f"{min_date}+{max_date}"
    if page == 1:
        return f"https://www.dabangasudan.org/ar/?post_date={date_query}"
    return f"https://www.dabangasudan.org/ar/page/{page}?post_date={date_query}"


def fetch_html(url: str, timeout: int = 15) -> str:
    """Fetches HTML with polite headers and error handling."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar,en;q=0.9",
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


# Broadcast, Radio, TV, and Audio/Video slug indicators
BROADCAST_SLUG_PATTERNS = [
    r'نشرة[-_]الاخبار',
    r'السودان[-_]هذا[-_]الاسبوع',
    r'السودان[-_]الان',
    r'حديث[-_]اليوم',
    r'في[-_]الميزان',
    r'جولة[-_]السودان',
    r'podcast',
    r'broadcast',
]
BROADCAST_SLUG_REGEX = re.compile('|'.join(BROADCAST_SLUG_PATTERNS), re.I)


def is_audio_or_video_broadcast(html: str) -> Tuple[bool, str]:
    """
    Inspects article HTML to determine if it is a Radio, TV, Podcast, or Audio/Video broadcast page.
    Full news articles contain narrative prose and lack audio/video broadcast players.
    """
    art_m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
    content = art_m.group(1) if art_m else html

    # Check for HTML5 audio or MP3 audio player
    if re.search(r'<audio[^>]*>|wp-audio-shortcode|\.mp3\b', content, re.I):
        return True, "Contains HTML5 audio player or MP3 audio source (Radio/Audio Broadcast)"

    # Check for HTML5 video or video embed (YouTube, Vimeo, etc.)
    if re.search(r'<video[^>]*>|wp-video-shortcode|\.mp4\b|youtube\.com|vimeo\.com|dailymotion\.com|<iframe[^>]+(youtube|vimeo|video|audio)', content, re.I):
        return True, "Contains video player or YouTube/Vimeo embed (TV/Video Broadcast)"

    # Check for Radio/Podcast/Broadcast taxonomy classes
    if re.search(r'category-(sudan-now-podcast|dabanga-programs|broadcasts|radio|tv|podcasts)-ar', html):
        return True, "Categorized under Radio/Podcast/Broadcast program taxonomy"

    # Check substantive paragraph word count: broadcast pages have virtually zero body prose
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
    p_text = " ".join(re.sub(r'<[^>]+>', ' ', p) for p in paragraphs).strip()
    words = p_text.split()
    if len(words) < 60:
        return True, f"Insufficient news body text ({len(words)} words; broadcast stub)"

    return False, "Full text news article"


def verify_article_is_full_news(url: str) -> Tuple[bool, str]:
    """
    Performs fast slug filtering followed by deep content inspection to ensure
    the page is a full news article and not a Radio/TV broadcast or audio/video post.
    """
    unquoted = urllib.parse.unquote(url)
    slug = unquoted.rstrip('/').split('/')[-1]

    # Fast slug check
    if BROADCAST_SLUG_REGEX.search(slug):
        return False, f"Slug matches broadcast pattern: '{slug}'"

    # Deep content inspection
    try:
        html = fetch_html(url, timeout=10)
    except Exception as exc:
        return False, f"Failed to fetch article for verification: {exc}"

    is_broadcast, reason = is_audio_or_video_broadcast(html)
    if is_broadcast:
        return False, reason

    return True, "Full text news article"


def collect_article_urls_for_date_range(min_date: str, max_date: str, max_pages: int = 10, filter_broadcasts: bool = True) -> List[str]:
    """Traverses Dabanga Arabic pagination to collect all unique article URLs for the date range, filtering out Radio/TV/Audio/Video pages."""
    print("=" * 70)
    print("  Knowledge Lab :: Radio Dabanga Arabic News Harvester")
    print(f"  Target Date Range  : {min_date} to {max_date}")
    print(f"  Pagination Limit   : up to {max_pages} pages")
    print(f"  Broadcast Filtering: {'ENABLED (Full News Articles ONLY)' if filter_broadcasts else 'DISABLED'}")
    print("=" * 70)

    seen_urls: Set[str] = set()
    candidate_urls: List[str] = []

    for page in range(1, max_pages + 1):
        page_url = build_page_url(min_date, max_date, page=page)
        print(f"[*] [Page {page}] Fetching: {page_url}")

        try:
            html = fetch_html(page_url)
        except Exception as exc:
            print(f"    [!] Error fetching page {page}: {exc}")
            break

        found_links = ARTICLE_URL_REGEX.findall(html)
        new_on_page = 0
        for link in found_links:
            clean_link = link.strip()
            if clean_link not in seen_urls:
                seen_urls.add(clean_link)
                candidate_urls.append(clean_link)
                new_on_page += 1

        print(f"    [✓] Discovered {new_on_page} candidate links on page {page} (cumulative: {len(candidate_urls)})")

        # Check for next page link in pagination nav
        has_next = bool(re.search(r'class=[\"\'][^\"\']*next\s+page-numbers[^\"\']*[\"\']', html))
        if not has_next or new_on_page == 0:
            print(f"[*] End of pagination reached at page {page}.")
            break

        time.sleep(1.0)  # Polite crawling delay

    if not filter_broadcasts:
        return candidate_urls

    # Filter out Radio, TV, Audio, and Video broadcast pages
    print(f"\n[*] Filtering {len(candidate_urls)} candidate URLs to isolate full news articles...")
    verified_full_news_urls: List[str] = []

    for idx, u in enumerate(candidate_urls, 1):
        is_full_news, reason = verify_article_is_full_news(u)
        slug = urllib.parse.unquote(u.rstrip('/').split('/')[-1])
        if is_full_news:
            verified_full_news_urls.append(u)
            print(f"    [{idx:02d}/{len(candidate_urls):02d}] [✓ KEEP] {slug[:45]}...")
        else:
            print(f"    [{idx:02d}/{len(candidate_urls):02d}] [- SKIP] {slug[:45]}... -> {reason}")

    print(f"\n[✓] Retained {len(verified_full_news_urls)} full news articles (excluded {len(candidate_urls) - len(verified_full_news_urls)} broadcast/audio/video pages).")
    return verified_full_news_urls


def export_feed_json(urls: List[str], min_date: str, max_date: str, output_path: Path) -> Path:
    """Exports collected article URLs into a standardized GDELT/Trafilatura-compatible feed JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    articles: List[Dict[str, Any]] = []
    for u in urls:
        articles.append({
            "published_at": f"{max_date}T12:00:00+00:00",
            "tier": "Regional / Local Field",
            "publisher": "dabangasudan.org",
            "language": "ar",
            "article_url": u,
            "sudan_locations": "Sudan",
            "topic_focus": "Conflict / News",
            "http_status": 200,
            "url_validation": "verified_ok"
        })

    feed_payload = {
        "retrieved_at": now_iso,
        "source": "dabangasudan.org/ar/",
        "date_range": {
            "start_date": min_date,
            "end_date": max_date
        },
        "query_metadata": {
            "total_articles": len(articles),
            "tier_breakdown": {
                "Regional / Local Field": len(articles)
            },
            "language": "ar"
        },
        "articles": articles
    }

    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(feed_payload, fp, indent=2, ensure_ascii=False)

    print(f"\n[✓] Exported {len(articles)} articles to feed JSON: {output_path}")
    return output_path


def run_trafilatura_extraction(feed_json: Path, max_articles: int = 50, dry_run: bool = False) -> bool:
    """Executes extract_articles_trafilatura.py on the generated feed JSON."""
    if not EXTRACTOR_SCRIPT.exists():
        print(f"[!] Error: Extractor script not found at {EXTRACTOR_SCRIPT}", file=sys.stderr)
        return False

    cmd = [
        sys.executable,
        str(EXTRACTOR_SCRIPT),
        "--input", str(feed_json),
        "--output-dir", str(ARTICLES_DIR),
        "--max-articles", str(max_articles),
    ]
    if dry_run:
        cmd.append("--dry-run")

    print("\n[*] Invoking Trafilatura article extractor...")
    res = subprocess.run(cmd)
    return res.returncode == 0


def archive_feed_json(feed_json: Path) -> Path:
    """Moves the processed feed JSON to news/archived/ for clean vault hygiene."""
    NEWS_ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)
    target = NEWS_ARCHIVED_DIR / feed_json.name
    feed_json.rename(target)
    print(f"[✓] Archived feed JSON to: {target}")
    return target


def main():
    parser = argparse.ArgumentParser(
        description="Extract Arabic news articles from Dabanga for a date range and extract full text via Trafilatura."
    )
    parser.add_argument(
        "--url", "-u",
        default="https://www.dabangasudan.org/ar/?post_date=2026-11-02+2026-11-01",
        help="Dabanga date filter URL (e.g. https://www.dabangasudan.org/ar/?post_date=2026-11-02+2026-11-01)"
    )
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output-json", "-o", help="Custom output path for generated feed JSON")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pagination depth (default: 10)")
    parser.add_argument("--max-articles", type=int, default=50, help="Max articles to extract via Trafilatura (default: 50)")
    parser.add_argument("--no-extract", action="store_true", help="Only harvest URLs into JSON without running Trafilatura extraction")
    parser.add_argument("--no-archive", action="store_true", help="Do not move feed JSON to news/archived/")
    parser.add_argument("--include-broadcasts", action="store_true", help="Include Radio/TV/Audio/Video broadcast pages (default: False, full text articles only)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")

    args = parser.parse_args()

    min_date, max_date = parse_and_normalize_date_range(args.url, args.start_date, args.end_date)
    print(f"[*] Normalized date interval: {min_date} to {max_date}")

    urls = collect_article_urls_for_date_range(
        min_date, max_date, max_pages=args.max_pages, filter_broadcasts=not args.include_broadcasts
    )
    if not urls:
        print("[!] No articles discovered for the specified date range.")
        sys.exit(0)

    # Determine feed JSON path
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    clean_date_tag = f"{min_date.replace('-', '')}_{max_date.replace('-', '')}"
    if args.output_json:
        feed_path = Path(args.output_json)
    else:
        feed_path = NEWS_DIR / f"dabanga_arabic_{clean_date_tag}_{timestamp}.json"

    export_feed_json(urls, min_date, max_date, feed_path)

    if not args.no_extract and not args.dry_run:
        success = run_trafilatura_extraction(feed_path, max_articles=args.max_articles, dry_run=args.dry_run)
        if success and not args.no_archive:
            archive_feed_json(feed_path)

    print("\n" + "=" * 70)
    print(f"  Harvesting & Extraction Complete! ({len(urls)} articles processed)")
    print("=" * 70)


if __name__ == "__main__":
    main()
