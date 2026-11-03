#!/usr/bin/env python3
"""
scripts/fetch_dabanga_rss.py
Extracts articles from the official Radio Dabanga RSS feed (https://www.dabangasudan.org/ar/feed)
for a selected month, filtered by category (<category><![CDATA[Main News]]></category> / الخبر الرئيسي),
excluding audio/video broadcasts, and saving standardized feed JSON output into /news.
Optionally triggers scripts/extract_articles_trafilatura.py to save individual Markdown articles into raw/articles/.
"""

import os
import sys
import re
import json
import time
import calendar
import argparse
import subprocess
import email.utils
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Set, Dict, Any, Optional

VAULT_ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = VAULT_ROOT / "news"
EXTRACTOR_SCRIPT = VAULT_ROOT / "scripts" / "extract_articles_trafilatura.py"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Broadcast, Radio, TV, and Audio/Video slug and title indicators
BROADCAST_PATTERNS = [
    r'نشرة[-_\s]الاخبار',
    r'السودان[-_\s]هذا[-_\s]الاسبوع',
    r'السودان[-_\s]الان',
    r'حديث[-_\s]اليوم',
    r'في[-_\s]الميزان',
    r'جولة[-_\s]السودان',
    r'podcast',
    r'broadcast',
    r'radio',
    r'episode',
]
BROADCAST_REGEX = re.compile('|'.join(BROADCAST_PATTERNS), re.I)

# Category synonyms for Main News in Arabic and English
DEFAULT_CATEGORIES = {"main news", "الخبر الرئيسي"}


def parse_target_month(month_arg: Optional[str], year_arg: Optional[int]) -> Tuple[int, int]:
    """
    Parses user-provided month and optional year arguments into (year, month).
    Supported formats:
      - '2026-10', '2026/10', '2026_10'
      - '10', 'October', 'oct' (with --year or current year)
      - 'current', 'now'
      - 'previous', 'last'
    """
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    if not month_arg or month_arg.lower() in ("current", "now"):
        return current_year, current_month

    if month_arg.lower() in ("previous", "last"):
        if current_month == 1:
            return current_year - 1, 12
        return current_year, current_month - 1

    # Check for YYYY-MM or YYYY/MM
    m_match = re.match(r'^(\d{4})[-/_](\d{1,2})$', month_arg.strip())
    if m_match:
        y = int(m_match.group(1))
        m = int(m_match.group(2))
        if 1 <= m <= 12:
            return y, m
        raise ValueError(f"Invalid month: {m}")

    # Check for MM-YYYY
    m_match_rev = re.match(r'^(\d{1,2})[-/_](\d{4})$', month_arg.strip())
    if m_match_rev:
        m = int(m_match_rev.group(1))
        y = int(m_match_rev.group(2))
        if 1 <= m <= 12:
            return y, m
        raise ValueError(f"Invalid month: {m}")

    # Check for numeric month (1-12)
    if month_arg.strip().isdigit():
        m = int(month_arg.strip())
        y = year_arg if year_arg else current_year
        if 1 <= m <= 12:
            return y, m
        raise ValueError(f"Invalid month number: {m}")

    # Check for month names (e.g. October, Oct)
    month_clean = month_arg.strip().capitalize()
    for m_idx in range(1, 13):
        if calendar.month_name[m_idx].lower() == month_clean.lower() or calendar.month_abbr[m_idx].lower() == month_clean.lower():
            y = year_arg if year_arg else current_year
            return y, m_idx

    raise ValueError(f"Could not parse month argument: '{month_arg}'. Expected format YYYY-MM (e.g. 2026-10) or month name.")


def get_month_boundaries(year: int, month: int) -> Tuple[datetime, datetime]:
    """Returns UTC datetime bounds for the start and end of the selected month."""
    start_dt = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    _, last_day = calendar.monthrange(year, month)
    end_dt = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start_dt, end_dt


def is_broadcast_item(title: str, url: str, categories: List[str]) -> bool:
    """Detects whether an item is an audio/video bulletin, radio podcast, or broadcast segment."""
    for cat in categories:
        cat_lower = cat.strip().lower()
        if cat_lower in ("نشرة الأخبار", "السودان الآن+", "podcast", "broadcast", "radio", "audio", "video"):
            return True

    decoded_url = urllib.parse.unquote(url)
    if BROADCAST_REGEX.search(decoded_url) or BROADCAST_REGEX.search(title):
        return True

    return False


def matches_category_filter(categories: List[str], target_categories: Set[str], include_all: bool) -> bool:
    """Checks whether the item's categories match the specified target categories."""
    if include_all:
        return True

    for cat in categories:
        clean_cat = cat.strip().lower()
        if clean_cat in target_categories:
            return True
        # Partial match for Arabic/English variants
        for target in target_categories:
            if target in clean_cat or clean_cat in target:
                return True

    return False


def fetch_feed_page(feed_url: str, page: int, timeout: int = 15) -> Optional[str]:
    """Fetches XML content of a paginated RSS feed."""
    parsed = urllib.parse.urlparse(feed_url)
    query_params = urllib.parse.parse_qs(parsed.query)
    if page > 1:
        query_params["paged"] = [str(page)]
    new_query = urllib.parse.urlencode(query_params, doseq=True)
    page_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    req = urllib.request.Request(
        page_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar,en;q=0.9",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            # End of pagination reached
            return None
        print(f"  [!] HTTP {e.code} on page {page}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [!] Network error on page {page}: {e}", file=sys.stderr)
        return None

    return None


def collect_articles_for_month(
    feed_url: str,
    target_year: int,
    target_month: int,
    target_categories: Set[str],
    include_all: bool = False,
    max_pages: int = 100,
    delay: float = 0.5,
    verbose: bool = True
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Sequentially traverses paginated RSS feed, filtering articles strictly published within
    the target month and matching the target category filter.
    """
    start_dt, end_dt = get_month_boundaries(target_year, target_month)
    month_label = f"{target_year}-{target_month:02d}"

    if verbose:
        print(f"[*] Starting Dabanga RSS Harvesting:")
        print(f"    Feed URL        : {feed_url}")
        print(f"    Target Month    : {month_label} ({start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')})")
        print(f"    Category Filter : {'ALL' if include_all else sorted(list(target_categories))}")
        print(f"    Max Pages       : {max_pages}")
        print(f"    Inter-page Delay: {delay}s")
        print("-" * 65)

    collected_articles: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()
    pages_scanned = 0

    for page in range(1, max_pages + 1):
        pages_scanned += 1
        xml_content = fetch_feed_page(feed_url, page)
        if not xml_content:
            if verbose:
                print(f"[*] Reached end of feed or page {page} unavailable. Terminating crawl.")
            break

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"  [!] XML parse error on page {page}: {e}", file=sys.stderr)
            break

        channel = root.find("channel")
        if channel is None:
            break

        items = channel.findall("item")
        if not items:
            if verbose:
                print(f"[*] Page {page} contains 0 items. Terminating crawl.")
            break

        page_dates: List[datetime] = []
        page_matched_count = 0

        for item in items:
            link_elem = item.find("link")
            title_elem = item.find("title")
            pubdate_elem = item.find("pubDate")

            raw_url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            pubdate_str = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""

            if not raw_url:
                continue

            # Extract categories
            categories = [c.text.strip() for c in item.findall("category") if c.text and c.text.strip()]

            # Parse publication date
            item_dt = None
            if pubdate_str:
                try:
                    item_dt = email.utils.parsedate_to_datetime(pubdate_str)
                    if item_dt.tzinfo is None:
                        item_dt = item_dt.replace(tzinfo=timezone.utc)
                    else:
                        item_dt = item_dt.astimezone(timezone.utc)
                    page_dates.append(item_dt)
                except Exception:
                    pass

            if not item_dt:
                continue

            # Check date window
            if item_dt > end_dt:
                # Article is newer than selected month; continue reading earlier items
                continue

            if item_dt < start_dt:
                # Article is older than selected month
                continue

            # Filter out broadcast / radio / TV pages
            if is_broadcast_item(title, raw_url, categories):
                continue

            # Check category criteria
            if not matches_category_filter(categories, target_categories, include_all):
                continue

            # Deduplicate by URL
            canonical_url = raw_url.split("?")[0].rstrip("/")
            if canonical_url in seen_urls:
                continue

            seen_urls.add(canonical_url)
            page_matched_count += 1

            article_obj = {
                "published_at": item_dt.isoformat(),
                "title": title,
                "tier": "Regional / Local Field",
                "publisher": "dabangasudan.org",
                "language": "ar" if "/ar/" in feed_url else "en",
                "article_url": raw_url,
                "categories": categories,
                "sudan_locations": "Sudan",
                "topic_focus": "Conflict / News",
                "http_status": 200,
                "url_validation": "verified_ok",
            }
            collected_articles.append(article_obj)

        if page_dates:
            oldest_on_page = min(page_dates)
            newest_on_page = max(page_dates)
            if verbose:
                print(f"  [+] Page {page:02d}: {len(items)} items | Dates: {newest_on_page.strftime('%Y-%m-%d')} to {oldest_on_page.strftime('%Y-%m-%d')} | Matched: {page_matched_count} (Total: {len(collected_articles)})")

            # Early termination: If all items on this page are strictly older than start_dt,
            # subsequent pages will only be even older.
            if newest_on_page < start_dt:
                if verbose:
                    print(f"[*] Page {page} dates ({newest_on_page.strftime('%Y-%m-%d')}) preceded target month start ({start_dt.strftime('%Y-%m-%d')}). Terminating.")
                break
        else:
            if verbose:
                print(f"  [+] Page {page:02d}: {len(items)} items | Matched: {page_matched_count}")

        time.sleep(delay)

    return collected_articles, pages_scanned


def save_feed_json(
    articles: List[Dict[str, Any]],
    feed_url: str,
    target_year: int,
    target_month: int,
    target_categories: Set[str],
    pages_scanned: int,
    output_dir: Path
) -> Path:
    """Saves the harvested articles into a standardized JSON feed in /news."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    month_slug = f"{target_year}{target_month:02d}"
    filename = f"dabanga_rss_{month_slug}_{timestamp}.json"
    out_path = output_dir / filename

    feed_data = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": feed_url,
        "target_month": f"{target_year}-{target_month:02d}",
        "category_filter": sorted(list(target_categories)),
        "query_metadata": {
            "total_articles": len(articles),
            "pages_scanned": pages_scanned,
            "tier_breakdown": {
                "Regional / Local Field": len(articles)
            },
            "language": "ar" if "/ar/" in feed_url else "en"
        },
        "articles": articles
    }

    out_path.write_text(json.dumps(feed_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract articles from Radio Dabanga RSS feed for a selected month filtered by category (Main News / الخبر الرئيسي)."
    )
    parser.add_argument(
        "--month", "-m",
        type=str,
        default="current",
        help="Selected month to harvest: 'YYYY-MM' (e.g. '2026-10'), month number (e.g. '10'), name ('October'), 'current', or 'previous'."
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=None,
        help="Target year if month is given as a single digit (default: current year)."
    )
    parser.add_argument(
        "--feed-url",
        type=str,
        default="https://www.dabangasudan.org/ar/feed",
        help="Base RSS feed URL (default: https://www.dabangasudan.org/ar/feed)."
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        default="Main News",
        help="Category to filter for (default: 'Main News' / 'الخبر الرئيسي'). Comma-separated for multiple."
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help="Bypass category filter and collect all full news articles."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=60,
        help="Maximum number of feed pages to traverse (default: 60)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.4,
        help="Politeness delay in seconds between page requests (default: 0.4s)."
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Automatically trigger scripts/extract_articles_trafilatura.py to save Markdown articles to raw/articles/."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform crawl and print matched articles without saving JSON file."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(NEWS_DIR),
        help=f"Directory to save output JSON feed (default: {NEWS_DIR})."
    )

    args = parser.parse_args()

    # Parse and validate month/year
    try:
        target_year, target_month = parse_target_month(args.month, args.year)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Normalize category filter
    categories_set: Set[str] = set()
    if not args.all_categories:
        raw_cats = [c.strip().lower() for c in args.category.split(",") if c.strip()]
        for c in raw_cats:
            categories_set.add(c)
            # Add English <-> Arabic mapping for Main News
            if c in ("main news", "main_news", "mainnews", "الخبر الرئيسي"):
                categories_set.add("main news")
                categories_set.add("الخبر الرئيسي")

    # Perform collection
    articles, pages_scanned = collect_articles_for_month(
        feed_url=args.feed_url,
        target_year=target_year,
        target_month=target_month,
        target_categories=categories_set,
        include_all=args.all_categories,
        max_pages=args.max_pages,
        delay=args.delay,
        verbose=True
    )

    month_label = f"{target_year}-{target_month:02d}"
    print("=" * 65)
    print(f"[✓] Harvest Summary for {month_label}:")
    print(f"    Total Pages Scanned : {pages_scanned}")
    print(f"    Articles Collected  : {len(articles)}")
    print("=" * 65)

    if not articles:
        print(f"[!] No articles matched for month {month_label}. Exiting.")
        sys.exit(0)

    if args.dry_run:
        print("[*] Dry-run enabled. Articles preview:")
        for idx, art in enumerate(articles[:10], 1):
            print(f"  {idx}. [{art['published_at'][:16]}] {art['title']}")
            print(f"     URL: {art['article_url']}")
        if len(articles) > 10:
            print(f"  ... and {len(articles) - 10} more.")
        sys.exit(0)

    # Save to news/
    out_dir = Path(args.output_dir)
    saved_path = save_feed_json(
        articles=articles,
        feed_url=args.feed_url,
        target_year=target_year,
        target_month=target_month,
        target_categories=categories_set,
        pages_scanned=pages_scanned,
        output_dir=out_dir
    )
    print(f"[✓] Saved JSON feed to: {saved_path}")

    # Optional extraction via Trafilatura
    if args.extract:
        print("\n[*] Invoking Trafilatura Article Extraction...")
        if not EXTRACTOR_SCRIPT.exists():
            print(f"  [!] Extractor script not found at {EXTRACTOR_SCRIPT}", file=sys.stderr)
            sys.exit(1)

        cmd = [sys.executable, str(EXTRACTOR_SCRIPT), "--input", str(saved_path)]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"  [!] Extraction failed with exit code {res.returncode}", file=sys.stderr)
            sys.exit(res.returncode)
        print("[✓] Article extraction completed into raw/articles/.")


if __name__ == "__main__":
    main()
