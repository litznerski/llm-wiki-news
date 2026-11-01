#!/usr/bin/env python3
"""
scripts/harvest_daily_news.py
End-to-End Orchestrator:
1. Harvests today's news from GDELT 2.0 via BigQuery (scripts/fetch_gdelt_bigquery.py).
2. Extracts full articles using Trafilatura into raw/articles/ (scripts/extract_articles_trafilatura.py).
3. Moves the processed JSON feed from news/ to news/archived/.
"""

import os
import sys
import shutil
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

VAULT_ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = VAULT_ROOT / "news"
ARCHIVED_DIR = NEWS_DIR / "archived"

# Auto-detect .venv site-packages if running with system python
for _sp in (VAULT_ROOT / ".venv" / "lib").glob("python3.*/site-packages"):
    if str(_sp) not in sys.path:
        sys.path.insert(0, str(_sp))


def run_pipeline(
    date: Optional[str] = None,
    days_ago: Optional[int] = None,
    project: Optional[str] = None,
    limit: int = 150,
    max_articles: int = 50,
    delay: float = 1.0,
    mock: bool = False,
    dry_run: bool = False,
) -> bool:
    """Executes the full GDELT harvest, Trafilatura extraction, and archive lifecycle."""
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    target_date = date or (today_utc if days_ago is None else None)

    ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)

    print("=======================================================================")
    print("  Knowledge Lab :: Daily News Harvester & Ingestion Pipeline")
    print(f"  Target Date      : {target_date or f'{days_ago} days ago'}")
    print(f"  BigQuery Limit   : {limit} records")
    print(f"  Extract Limit    : {max_articles} articles")
    print(f"  Execution Mode   : {'MOCK' if mock else 'LIVE BIGQUERY'} | {'DRY-RUN' if dry_run else 'PERSIST'}")
    print("=======================================================================")

    # Step 1: Run GDELT BigQuery Harvester
    print("\n[Step 1/3] Harvesting news metadata from GDELT 2.0...")
    timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date_tag = target_date or f"dminus{days_ago}"
    out_json = NEWS_DIR / f"gdelt_sudan_{date_tag}_{timestamp_tag}.json"

    fetch_cmd = [
        sys.executable,
        str(VAULT_ROOT / "scripts" / "fetch_gdelt_bigquery.py"),
        "--output-file", str(out_json),
        "--limit", str(limit),
    ]

    if target_date:
        fetch_cmd.extend(["--date", target_date])
    elif days_ago is not None:
        fetch_cmd.extend(["--days-ago", str(days_ago)])

    if project:
        fetch_cmd.extend(["--project", project])

    if mock:
        fetch_cmd.append("--mock")

    proc = subprocess.run(fetch_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[!] Error in fetch_gdelt_bigquery.py:\n{proc.stderr}", file=sys.stderr)
        return False
    print(proc.stdout.strip())

    if not out_json.exists() or out_json.stat().st_size == 0:
        print(f"[!] Expected output JSON was not created: {out_json}", file=sys.stderr)
        return False

    # Step 2: Extract Articles via Trafilatura
    print("\n[Step 2/3] Extracting full-text articles via Trafilatura to raw/articles/...")
    extract_cmd = [
        sys.executable,
        str(VAULT_ROOT / "scripts" / "extract_articles_trafilatura.py"),
        "--input", str(out_json),
        "--max-articles", str(max_articles),
        "--delay", str(delay),
    ]
    if dry_run:
        extract_cmd.append("--dry-run")

    proc = subprocess.run(extract_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[!] Error in extract_articles_trafilatura.py:\n{proc.stderr}", file=sys.stderr)
        return False
    print(proc.stdout.strip())

    # Step 3: Archive Processed JSON Feed
    print("\n[Step 3/3] Archiving processed JSON feed...")
    dest_json = ARCHIVED_DIR / out_json.name

    # Handle collision if file already exists in archive
    col_idx = 1
    while dest_json.exists():
        dest_json = ARCHIVED_DIR / f"{out_json.stem}_{col_idx}.json"
        col_idx += 1

    shutil.move(str(out_json), str(dest_json))
    print(f"  [✓] Moved feed: {out_json.name} -> news/archived/{dest_json.name}")

    print("\n=======================================================================")
    print("  [✓] Daily News Pipeline Successfully Completed!")
    print(f"      - Feed archived : {dest_json.relative_to(VAULT_ROOT)}")
    print(f"      - Raw articles  : raw/articles/")
    print("      - Next action   : Run '/scope' or '/ingest' on newly added articles")
    print("=======================================================================")
    return True


def main():
    parser = argparse.ArgumentParser(description="Harvest today's Sudan news, extract articles via Trafilatura, and archive feed.")
    parser.add_argument("--date", help="Target publication date (YYYY-MM-DD). Defaults to today's date in UTC.")
    parser.add_argument("--days-ago", type=int, help="Scan partition N days in the past (overrides default today).")
    parser.add_argument("--project", help="Google Cloud project ID for BigQuery execution.")
    parser.add_argument("--limit", type=int, default=150, help="Maximum articles to return from BigQuery (default: 150).")
    parser.add_argument("--max-articles", type=int, default=50, help="Maximum articles to fetch via Trafilatura (default: 50).")
    parser.add_argument("--delay", type=float, default=1.0, help="Polite delay between HTTP requests in seconds (default: 1.0s).")
    parser.add_argument("--mock", action="store_true", help="Run with synthetic GDELT data (for offline testing).")
    parser.add_argument("--dry-run", action="store_true", help="Run Trafilatura in dry-run mode without saving files.")
    args = parser.parse_args()

    success = run_pipeline(
        date=args.date,
        days_ago=args.days_ago,
        project=args.project,
        limit=args.limit,
        max_articles=args.max_articles,
        delay=args.delay,
        mock=args.mock,
        dry_run=args.dry_run,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
