#!/usr/bin/env python3
"""
scripts/fetch_gdelt_bigquery.py
Harvests high-relevance Sudan conflict and war economy news from GDELT 2.0 Global Knowledge Graph
via Google BigQuery (gdelt-bq.gdeltv2.gkg_partitioned), verifies live URLs in parallel,
and exports structured feeds to news/.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Auto-detect .venv site-packages if running with system python
for _sp in (VAULT_ROOT / ".venv" / "lib").glob("python3.*/site-packages"):
    if str(_sp) not in sys.path:
        sys.path.insert(0, str(_sp))

# Sourcing .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


def build_gdelt_query(days_ago: int = 3, explicit_date: Optional[str] = None, limit: int = 150) -> str:
    """
    Constructs the partition-optimized, deduplicated BigQuery SQL for GDELT 2.0 GKG
    across both English (gkg_partitioned) and Translingual/Arabic (gkg_translingual_partitioned),
    including ALL Arabic articles from Radio Dabanga (dabangasudan.org / dabanga.org).
    """
    if explicit_date:
        partition_filter = f"_PARTITIONDATE = '{explicit_date}'"
    else:
        partition_filter = f"_PARTITIONDATE = DATE_SUB(CURRENT_DATE(), INTERVAL {days_ago} DAY)"

    query = f"""
WITH verified_publishers AS (
  SELECT domain, tier FROM UNNEST([
    -- 1. Global Wire Services & Major Fact-Checking Outlets
    STRUCT('reuters.com' AS domain, 'Tier 1 Wire' AS tier),
    STRUCT('apnews.com', 'Tier 1 Wire'),
    STRUCT('afp.com', 'Tier 1 Wire'),
    STRUCT('bbc.com', 'Tier 1 International'),
    STRUCT('bbc.co.uk', 'Tier 1 International'),
    STRUCT('aljazeera.com', 'Tier 1 International'),
    STRUCT('theguardian.com', 'Tier 1 International'),
    STRUCT('dw.com', 'Tier 1 International'),
    STRUCT('france24.com', 'Tier 1 International'),
    -- 2. Respected Sudan-Focused & Regional Media
    STRUCT('dabangasudan.org', 'Regional / Local Field'),
    STRUCT('dabanga.org', 'Regional / Local Field'),
    STRUCT('sudantribune.com', 'Regional / Local Field'),
    STRUCT('3ayin.com', 'Regional / Local Field'),
    STRUCT('sudanspost.com', 'Regional / Local Field')
  ])
),

-- Filter strictly on the target date partition against gkg_partitioned
filtered_articles AS (
  SELECT
    g.DATE,
    g.SourceCollectionIdentifier,
    g.SourceCommonName,
    g.DocumentIdentifier,
    g.V2Locations,
    g.V2Themes,
    g.V2Persons,
    g.V2Tone,
    g.TranslationInfo,
    vp.tier,
    -- Detect Arabic articles via GDELT TranslationInfo ('srclc:ara') or Dabanga '/ar/' URL structure
    (
      IFNULL(g.TranslationInfo, '') LIKE '%srclc:ara%'
      OR REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'(/ar/|%[d89][0-9a-f])')
    ) AS is_arabic,
    (
      g.SourceCommonName IN ('dabangasudan.org', 'dabanga.org')
      AND (
        IFNULL(g.TranslationInfo, '') LIKE '%srclc:ara%'
        OR REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'(/ar/|%[d89][0-9a-f])')
      )
      AND NOT REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'/en/')
    ) AS is_dabanga_arabic
  FROM
    `gdelt-bq.gdeltv2.gkg_partitioned` g
  JOIN
    verified_publishers vp
  ON
    g.SourceCommonName = vp.domain
  WHERE
    {partition_filter}
    AND g.SourceCollectionIdentifier = 1
    AND REGEXP_CONTAINS(g.DocumentIdentifier, r'^https?://')
)

SELECT
  PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(g.DATE AS STRING)) AS published_at,
  g.tier,
  g.SourceCommonName AS publisher,
  IF(g.is_arabic, 'ar', 'en') AS language,
  g.DocumentIdentifier AS article_url,

  -- Extracts and displays ONLY Sudan-specific locations (strips Washington, Cairo, Geneva, etc.)
  (
    SELECT STRING_AGG(DISTINCT REGEXP_EXTRACT(loc, r'^[1-5]#([^#]+)#'), '; ')
    FROM UNNEST(SPLIT(g.V2Locations, ';')) AS loc
    WHERE REGEXP_CONTAINS(loc, r'^[1-5]#[^#]+#SU#')
  ) AS sudan_locations,

  -- Dynamic Classification: War Economy, Economy & Livelihoods, Security / Conflict, or General (for unfiltered Dabanga AR)
  CASE
    WHEN (
      g.V2Themes LIKE '%ECON%' OR g.V2Themes LIKE '%POVERTY%' OR g.V2Themes LIKE '%AGRICULTURE%'
      OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),
        r'(econom|inflat|currenc|pound|sdg|exchange[-_]?rate|bank|food[-_]?price|cash|remittanc|livelihood|gold|trade|salary|salaries)')
    ) AND (
      g.V2Themes LIKE '%ARMEDCONFLICT%' OR g.V2Themes LIKE '%WAR%' OR g.V2Themes LIKE '%MILITARY%' OR g.V2Themes LIKE '%AIRSTRIKE%'
      OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),
        r'(rsf|rapid[-_]?support|saf|burhan|hemedti|dagalo|clash|bombardment|drone|shelling|airstrike)')
    ) THEN 'War Economy / Intersect'
    WHEN (
      g.V2Themes LIKE '%ECON%' OR g.V2Themes LIKE '%POVERTY%' OR g.V2Themes LIKE '%AGRICULTURE%'
      OR REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),
        r'(econom|inflat|currenc|pound|sdg|exchange[-_]?rate|bank|food[-_]?price|cash|remittanc|livelihood|gold|trade|salary|salaries)')
    ) THEN 'Economy & Livelihoods'
    WHEN (
      g.V2Themes LIKE '%ARMEDCONFLICT%' OR g.V2Themes LIKE '%WAR%' OR g.V2Themes LIKE '%MILITARY%' OR g.V2Themes LIKE '%AIRSTRIKE%'
      OR g.V2Themes LIKE '%DRONE%' OR g.V2Themes LIKE '%DISPLACEMENT%' OR g.V2Themes LIKE '%HUMAN_RIGHTS_ABUSES%'
    ) THEN 'Security / Conflict'
    WHEN g.is_dabanga_arabic THEN 'Sudan General / Arabic Feed'
    ELSE 'Security / Conflict'
  END AS topic_focus,

  -- Sentiment score (-10 to +10)
  CAST(SPLIT(g.V2Tone, ',')[OFFSET(0)] AS FLOAT64) AS tone_score,
  g.V2Themes AS themes

FROM
  filtered_articles g
WHERE
  -- PATH A: Include ALL Arabic news from Dabanga in the selected time frame unconditionally
  g.is_dabanga_arabic = TRUE

  -- PATH B: Standard strict Sudan location + Conflict/Economic filter for all other sources
  OR (
    -- 1. Strict Sudan Geographic Requirement (FIPS 'SU')
    REGEXP_CONTAINS(g.V2Locations, r'(^|;)[1-5]#[^#]+#SU#')

    -- 2. Geographic & Entity Exclusions (South Sudan 'OD' and Iraqi PM Al-Sudani)
    AND g.V2Locations NOT LIKE '%#OD#%'
    AND NOT REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'south[-_]?sudan')
    AND NOT REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Persons, ''))), r'al[-_ ]?sudani')

    -- 3. Thematic Filter: Conflict OR Economic Crisis
    AND (
      g.V2Themes LIKE '%ARMEDCONFLICT%'
      OR g.V2Themes LIKE '%WAR%'
      OR g.V2Themes LIKE '%MILITARY%'
      OR g.V2Themes LIKE '%AIRSTRIKE%'
      OR g.V2Themes LIKE '%DRONE%'
      OR g.V2Themes LIKE '%DISPLACEMENT%'
      OR g.V2Themes LIKE '%HUMAN_RIGHTS_ABUSES%'
      OR g.V2Themes LIKE '%ECON_%'
      OR g.V2Themes LIKE '%ECONOMY%'
      OR g.V2Themes LIKE '%POVERTY%'
      OR g.V2Themes LIKE '%AGRICULTURE%'
      OR g.V2Themes LIKE '%UNGP_FORECAST_FAMINE%'
      OR g.V2Themes LIKE '%WB_470_MACROECONOMIC_VULNERABILITY%'
      OR g.V2Themes LIKE '%WB_530_FINANCIAL_SECTOR_DEVELOPMENT%'
      OR REGEXP_CONTAINS(
        LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Themes, ''))),
        r'(rsf|rapid[-_]?support|saf|burhan|hemedti|dagalo|clash|bombardment|drone|shelling|airstrike|ceasefire|paramilitary|darfur|kordofan|gezira|el[-_]?fasher|econom|inflat|currenc|exchange[-_]?rate|sudanese[-_]?pound|sdg|bank|banking|cash[-_]?crisis|remittanc|food[-_]?price|famine|livelihood|gold[-_]?mining|gold[-_]?smuggling|wages|salary|salaries)'
      )
    )
  )
-- Deduplicate identical URLs within the partition
QUALIFY ROW_NUMBER() OVER (PARTITION BY g.DocumentIdentifier ORDER BY g.DATE DESC) = 1
ORDER BY
  published_at DESC
LIMIT {limit};
"""
    return query


def _check_single_url(url: str, timeout: float = 8.0, strict_http: bool = False) -> Tuple[bool, str, int, str]:
    """
    Checks a single URL via HEAD, falling back to ranged GET if rejected.
    Returns: (is_valid, resolved_url, http_status, status_label)
    """
    for method in ("HEAD", "GET"):
        headers = dict(BROWSER_HEADERS)
        if method == "GET":
            headers["Range"] = "bytes=0-1024"

        req = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode() or 200
                final_url = resp.geturl() or url
                return True, final_url, status, "verified_ok"
        except urllib.error.HTTPError as e:
            # If HEAD returns 405/403/404/400, retry with GET before declaring dead
            if method == "HEAD" and e.code in (400, 403, 404, 405, 501):
                continue

            # Definite dead links
            if e.code in (404, 410):
                return False, url, e.code, "dead_404"

            # WAF / Bot protection (Cloudflare/DataDome on Reuters, Sudan Tribune, etc.)
            if e.code in (401, 403, 429):
                if strict_http:
                    return False, url, e.code, "blocked_waf"
                return True, url, e.code, "waf_protected"

            return False, url, e.code, f"http_error_{e.code}"
        except Exception:
            if method == "HEAD":
                continue
            return False, url, 0, "connection_failed"

    return False, url, 0, "unreachable"


def verify_and_resolve_urls(
    articles: List[Dict[str, Any]],
    max_workers: int = 16,
    timeout: float = 8.0,
    strict_http: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Validates article URLs in parallel, drops 404s, and updates redirected URLs.
    """
    if not articles:
        return [], {}

    print(f"[*] Verifying {len(articles)} URLs in parallel (workers={max_workers}, timeout={timeout}s)...")
    valid_articles: List[Dict[str, Any]] = []
    stats: Dict[str, int] = {
        "verified_ok": 0,
        "waf_protected": 0,
        "dead_404": 0,
        "other_dropped": 0,
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(_check_single_url, a["article_url"], timeout, strict_http): a
            for a in articles
            if a.get("article_url")
        }

        for future in as_completed(future_to_article):
            article = future_to_article[future]
            orig_url = article["article_url"]
            is_valid, final_url, code, label = future.result()

            if is_valid:
                article["article_url"] = final_url
                if final_url != orig_url:
                    article["original_gdelt_url"] = orig_url
                article["http_status"] = code
                article["url_validation"] = label
                valid_articles.append(article)
                stats[label] = stats.get(label, 0) + 1
            else:
                if label == "dead_404":
                    stats["dead_404"] += 1
                else:
                    stats["other_dropped"] += 1

    # Restore chronological sort order after async completion
    valid_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return valid_articles, stats


def generate_mock_data(days_ago: int = 3, explicit_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generates synthetic GDELT data conforming to the SQL schema for testing/dry-run."""
    date_str = explicit_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "published_at": f"{date_str}T14:32:00Z",
            "tier": "Regional / Local Field",
            "publisher": "dabangasudan.org",
            "article_url": "https://www.dabangasudan.org/en/all-news/article/sudan-drone-strike-targets-power-station-in-el-obeid",
            "sudan_locations": "El Obeid; North Kordofan",
            "topic_focus": "Security / Conflict",
            "tone_score": -6.42,
            "themes": "ARMEDCONFLICT;MILITARY;AIRSTRIKE;DRONE;INFRASTRUCTURE;",
        },
        {
            "published_at": f"{date_str}T12:15:00Z",
            "tier": "Tier 1 Wire",
            "publisher": "reuters.com",
            "article_url": "https://www.reuters.com/world/africa/sudans-soaring-inflation-deepens-war-economy-crisis-2026-10-29/",
            "sudan_locations": "Port Sudan; Khartoum",
            "topic_focus": "War Economy / Intersect",
            "tone_score": -4.85,
            "themes": "ECON_INFLATION;CURRENCY;ARMEDCONFLICT;WB_470_MACROECONOMIC_VULNERABILITY;",
        },
        {
            "published_at": f"{date_str}T10:05:00Z",
            "tier": "Regional / Local Field",
            "publisher": "sudantribune.com",
            "article_url": "https://sudantribune.com/article293021/clashes-erupt-near-zamzam-camp-in-north-darfur/",
            "sudan_locations": "El Fasher; Zamzam; North Darfur",
            "topic_focus": "Security / Conflict",
            "tone_score": -8.12,
            "themes": "ARMEDCONFLICT;WAR;DISPLACEMENT;HUMAN_RIGHTS_ABUSES;",
        },
        {
            "published_at": f"{date_str}T08:45:00Z",
            "tier": "Tier 1 International",
            "publisher": "aljazeera.com",
            "article_url": "https://www.aljazeera.com/news/2026/10/29/un-warns-of-catastrophic-famine-in-darfur-and-kordofan",
            "sudan_locations": "Darfur; Kordofan; Geneina",
            "topic_focus": "Economy & Livelihoods",
            "tone_score": -7.30,
            "themes": "UNGP_FORECAST_FAMINE;AGRICULTURE;POVERTY;FOOD_SECURITY;",
        },
        {
            "published_at": f"{date_str}T06:20:00Z",
            "tier": "Regional / Local Field",
            "publisher": "3ayin.com",
            "article_url": "https://3ayin.com/en/darfur-gold-smuggling-networks-fund-paramilitary-campaigns/",
            "sudan_locations": "Nyala; South Darfur; Jebel Amer",
            "topic_focus": "War Economy / Intersect",
            "tone_score": -5.10,
            "themes": "ECONOMY;GOLD_MINING;ARMEDCONFLICT;MILITARY_FINANCING;",
        },
    ]


def execute_bigquery_query(sql: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Connects to Google Cloud BigQuery and executes the GDELT query."""
    try:
        from google.cloud import bigquery
    except ImportError:
        print("[!] Error: 'google-cloud-bigquery' is not installed.", file=sys.stderr)
        print("    Install it via: pip install google-cloud-bigquery", file=sys.stderr)
        print("    Or run with --mock for offline validation.", file=sys.stderr)
        sys.exit(1)

    project = project_id or os.getenv("GCP_PROJECT_ID") or os.getenv("BIGQUERY_PROJECT_ID")
    if not project:
        print("[!] Notice: No GCP Project ID specified in CLI or .env.", file=sys.stderr)
        print("    BigQuery requires a project ID for billing/quota tracking even for public datasets.", file=sys.stderr)
        print("    Set GCP_PROJECT_ID=your-project in .env or pass --project <id>.", file=sys.stderr)

    client = bigquery.Client(project=project)
    print(f"[*] Executing query against GDELT v2 GKG (Project: {client.project or 'default'})...")

    query_job = client.query(sql)
    results = query_job.result()

    rows = []
    for row in results:
        published_at = row.get("published_at")
        if isinstance(published_at, datetime):
            pub_str = published_at.isoformat()
        else:
            pub_str = str(published_at) if published_at else ""

        rows.append({
            "published_at": pub_str,
            "tier": row.get("tier"),
            "publisher": row.get("publisher"),
            "language": row.get("language") or "en",
            "article_url": row.get("article_url"),
            "sudan_locations": row.get("sudan_locations") or "",
            "topic_focus": row.get("topic_focus"),
            "tone_score": row.get("tone_score"),
            "themes": row.get("themes") or "",
        })

    return rows


def main():
    parser = argparse.ArgumentParser(description="Harvest Sudan conflict news from GDELT 2.0 via Google BigQuery.")
    parser.add_argument("--project", help="Google Cloud project ID for BigQuery execution.")
    parser.add_argument("--days-ago", type=int, default=3, help="Scan partition N days in the past (default: 3).")
    parser.add_argument("--date", help="Explicit partition date (YYYY-MM-DD), overrides --days-ago.")
    parser.add_argument("--limit", type=int, default=150, help="Maximum articles to return (default: 150).")
    parser.add_argument("--output-dir", default=str(VAULT_ROOT / "news"), help="Directory to save JSON output (default: news/).")
    parser.add_argument("--output-file", help="Explicit filename/path for JSON output.")
    parser.add_argument("--mock", action="store_true", help="Run with synthetic GDELT data (for offline testing).")
    parser.add_argument("--skip-verify", action="store_true", help="Skip parallel HTTP 404/redirect verification.")
    parser.add_argument("--strict-http", action="store_true", help="Drop 403/429 WAF-protected links as well as 404s.")
    parser.add_argument("--workers", type=int, default=16, help="Number of parallel threads for URL verification.")
    parser.add_argument("--print-sql", action="store_true", help="Print the generated SQL query and exit.")
    args = parser.parse_args()

    sql = build_gdelt_query(days_ago=args.days_ago, explicit_date=args.date, limit=args.limit)

    if args.print_sql:
        print("=" * 70)
        print("  Generated GDELT BigQuery SQL")
        print("=" * 70)
        print(sql)
        sys.exit(0)

    partition_label = args.date or f"minus_{args.days_ago}_days"

    print("=" * 70)
    print("  Knowledge Lab :: GDELT 2.0 BigQuery News Harvester")
    print(f"  Target Partition : {partition_label}")
    print(f"  Query Limit      : {args.limit} articles")
    print(f"  Execution Mode   : {'MOCK / DRY-RUN (Synthetic URLs)' if args.mock else 'LIVE BIGQUERY'}")
    print("=" * 70)

    if args.mock:
        articles = generate_mock_data(days_ago=args.days_ago, explicit_date=args.date)
        print(f"  [!] Loaded {len(articles)} synthetic mock articles (URLs are fake placeholders).")
        validation_stats = {"mock_mode_unverified": len(articles)}
    else:
        try:
            articles = execute_bigquery_query(sql, project_id=args.project)
            print(f"  [✓] BigQuery returned {len(articles)} candidate articles.")
        except Exception as e:
            print(f"  [!] BigQuery execution failed: {e}", file=sys.stderr)
            print("      Tip: Run with --mock to test the pipeline with synthetic data.", file=sys.stderr)
            sys.exit(1)

        if not args.skip_verify and articles:
            articles, validation_stats = verify_and_resolve_urls(
                articles,
                max_workers=args.workers,
                strict_http=args.strict_http,
            )
            print(
                f"  [✓] URL Verification complete: {len(articles)} kept "
                f"(OK: {validation_stats.get('verified_ok', 0)}, "
                f"WAF-Protected: {validation_stats.get('waf_protected', 0)}, "
                f"Dropped 404s: {validation_stats.get('dead_404', 0)}, "
                f"Dropped Other: {validation_stats.get('other_dropped', 0)})"
            )
        else:
            validation_stats = {"verification_skipped": len(articles)}

    # Compute telemetry
    tier_counts = {}
    topic_counts = {}
    for a in articles:
        tier = a.get("tier", "Unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        topic = a.get("topic_focus", "Unknown")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    payload = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "partition_date": args.date or f"DATE_SUB(CURRENT_DATE(), INTERVAL {args.days_ago} DAY)",
        "query_metadata": {
            "total_articles": len(articles),
            "url_validation_breakdown": validation_stats,
            "tier_breakdown": tier_counts,
            "topic_focus_breakdown": topic_counts,
        },
        "articles": articles,
    }

    # Determine output path
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.output_file:
        out_file = Path(args.output_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        date_tag = args.date or f"dminus{args.days_ago}"
        out_file = out_dir / f"gdelt_sudan_{date_tag}_{timestamp_tag}.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("")
    print(f"  [✓] Exported {len(articles)} verified articles to: {out_file}")
    print(f"      - Tier breakdown: {tier_counts}")
    print(f"      - Topic breakdown: {topic_counts}")
    print("=================================================================")


if __name__ == "__main__":
    main()
