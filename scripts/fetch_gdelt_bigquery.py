#!/usr/bin/env python3
"""
scripts/fetch_gdelt_bigquery.py
Harvests high-relevance Sudan conflict and war economy news from GDELT 2.0 Global Knowledge Graph
via Google BigQuery (gdelt-bq.gdeltv2.gkg_partitioned) and exports structured feeds to news/.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VAULT_ROOT = Path(__file__).resolve().parent.parent

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


def build_gdelt_query(days_ago: int = 3, explicit_date: Optional[str] = None, limit: int = 150) -> str:
    """Constructs the partition-optimized BigQuery SQL for GDELT 2.0 GKG."""
    if explicit_date:
        partition_filter = f"g._PARTITIONDATE = '{explicit_date}'"
    else:
        partition_filter = f"g._PARTITIONDATE = DATE_SUB(CURRENT_DATE(), INTERVAL {days_ago} DAY)"

    query = f"""
WITH verified_publishers AS (
  SELECT domain, tier FROM UNNEST([
    -- 1. Global Wire Services & Major Fact-Checking Outlets
    STRUCT('reuters.com' AS domain, 'Tier 1 Wire' AS tier),
    STRUCT('apnews.com', 'Tier 1 Wire'),
    STRUCT('afp.com', 'Tier 1 Wire'),
    STRUCT('bbc.com', 'Tier 1 International'),
    STRUCT('aljazeera.com', 'Tier 1 International'),
    STRUCT('theguardian.com', 'Tier 1 International'),
    STRUCT('dw.com', 'Tier 1 International'),
    STRUCT('france24.com', 'Tier 1 International'),
    -- 2. Respected Sudan-Focused & Regional Media
    STRUCT('dabangasudan.org', 'Regional / Local Field'),
    STRUCT('sudantribune.com', 'Regional / Local Field'),
    STRUCT('ayinp.net', 'Regional / Local Field'),
    STRUCT('sudanspost.com', 'Regional / Local Field')
  ])
)

SELECT
  PARSE_TIMESTAMP('%Y%m%d%H%M%S', CAST(g.DATE AS STRING)) AS published_at,
  vp.tier,
  g.SourceCommonName AS publisher,
  g.DocumentIdentifier AS article_url,

  -- Extracts and displays ONLY Sudan-specific locations (strips Washington, Cairo, Geneva, etc.)
  (
    SELECT STRING_AGG(DISTINCT REGEXP_EXTRACT(loc, r'^[1-5]#([^#]+)#'), '; ')
    FROM UNNEST(SPLIT(g.V2Locations, ';')) AS loc
    WHERE REGEXP_CONTAINS(loc, r'^[1-5]#[^#]+#SU#')
  ) AS sudan_locations,

  -- Dynamic Classification: War Economy, Economy & Livelihoods, or Security / Conflict
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
    ELSE 'Security / Conflict'
  END AS topic_focus,

  -- Sentiment score (-10 to +10)
  CAST(SPLIT(g.V2Tone, ',')[OFFSET(0)] AS FLOAT64) AS tone_score,
  g.V2Themes AS themes

FROM
  `gdelt-bq.gdeltv2.gkg_partitioned` g
JOIN
  verified_publishers vp
ON
  g.SourceCommonName = vp.domain
WHERE
  -- 1. Date Partition: Scans strictly targeted 24-hour shard
  {partition_filter}

  -- 2. Strict Sudan Geographic Requirement (FIPS 'SU')
  AND REGEXP_CONTAINS(g.V2Locations, r'(^|;)[1-5]#[^#]+#SU#')

  -- 3. Geographic & Entity Exclusions (South Sudan 'OD' and Iraqi PM Al-Sudani)
  AND g.V2Locations NOT LIKE '%#OD#%'
  AND NOT REGEXP_CONTAINS(LOWER(g.DocumentIdentifier), r'south[-_]?sudan')
  AND NOT REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(g.DocumentIdentifier, ''), ' ', IFNULL(g.V2Persons, ''))), r'al[-_ ]?sudani')

  -- 4. Thematic Filter: Conflict OR Economic Crisis
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
ORDER BY
  published_at DESC
LIMIT {limit};
"""
    return query


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
            "publisher": "ayinp.net",
            "article_url": "https://ayinp.net/en/darfur-gold-smuggling-networks-fund-paramilitary-campaigns/",
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
    print(f"  Execution Mode   : {'MOCK / DRY-RUN' if args.mock else 'LIVE BIGQUERY'}")
    print("=" * 70)

    if args.mock:
        articles = generate_mock_data(days_ago=args.days_ago, explicit_date=args.date)
        print(f"  [✓] Loaded {len(articles)} synthetic articles for testing.")
    else:
        try:
            articles = execute_bigquery_query(sql, project_id=args.project)
            print(f"  [✓] BigQuery returned {len(articles)} matching articles.")
        except Exception as e:
            print(f"  [!] BigQuery execution failed: {e}", file=sys.stderr)
            print("      Tip: Run with --mock to test the pipeline with synthetic data.", file=sys.stderr)
            sys.exit(1)

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
    print(f"  [✓] Exported {len(articles)} articles to: {out_file}")
    print(f"      - Tier breakdown: {tier_counts}")
    print(f"      - Topic breakdown: {topic_counts}")
    print("=================================================================")


if __name__ == "__main__":
    main()
