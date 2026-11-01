---
name: gdelt-news-fetch
description: Extracts today's Sudan conflict and war economy news from GDELT 2.0 via Google BigQuery, extracts full articles using Trafilatura into raw/articles/ with deduplication, and archives the processed feed JSON into news/archived/.
---

# GDELT Daily News Fetch Skill (`gdelt-news-fetch`)

## Objective
Automates the discovery, extraction, and staging of high-relevance Sudan conflict, war economy, and humanitarian news from the **GDELT 2.0 Global Knowledge Graph (`gdelt-bq.gdeltv2.gkg_partitioned`)** into the local repository:
1. Harvests news metadata for today (or a specified partition date) from Google BigQuery using [`scripts/fetch_gdelt_bigquery.py`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/scripts/fetch_gdelt_bigquery.py).
2. Extracts clean, full-text markdown articles using Trafilatura via [`scripts/extract_articles_trafilatura.py`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/scripts/extract_articles_trafilatura.py), enforcing deduplication against [`raw/articles/`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/raw/articles/).
3. Upon successful extraction, moves the processed feed JSON file from `news/` into `news/archived/`.

---

## Trigger When
- The user requests to:
  - *"Extract today's news"*
  - *"Pull news from GDELT"*
  - *"Check for new Sudan conflict articles"*
  - *"Harvest recent reporting on Sudan"*
- Setting up a morning SITREP or scheduled intelligence collection cycle.

---

## Execution Options

### Option A: Unified Orchestration (Recommended)
Run the consolidated orchestrator script [`scripts/harvest_daily_news.py`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/scripts/harvest_daily_news.py), which automatically executes the 3-step pipeline and moves the feed JSON to `news/archived/`:

```bash
# Harvest today's news (UTC)
python3 scripts/harvest_daily_news.py

# Harvest news from a specific date (YYYY-MM-DD)
python3 scripts/harvest_daily_news.py --date 2026-11-01

# Harvest yesterday's full 24-hour partition
python3 scripts/harvest_daily_news.py --days-ago 1

# Limit number of articles extracted via Trafilatura
python3 scripts/harvest_daily_news.py --max-articles 30

# Test run using synthetic mock data (offline / without GCP credentials)
python3 scripts/harvest_daily_news.py --mock --dry-run
```

---

### Option B: Step-by-Step Manual Invocation

#### Step 1: Query GDELT 2.0 via Google BigQuery
Execute the partition-scoped SQL query to harvest news metadata:
```bash
# Query today's partition and export to news/
python3 scripts/fetch_gdelt_bigquery.py --days-ago 0

# Or target an explicit partition date:
python3 scripts/fetch_gdelt_bigquery.py --date 2026-11-01
```
*Output*: Generates `news/gdelt_sudan_<date>_<timestamp>.json`.

#### Step 2: Extract Articles via Trafilatura
Pass the generated JSON to the Trafilatura extractor:
```bash
python3 scripts/extract_articles_trafilatura.py --input news/gdelt_sudan_<date>_<timestamp>.json --max-articles 50
```
- **Deduplication Sentinel**: Automatically checks existing notes in [`raw/articles/`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/raw/articles/) by frontmatter `source: "<URL>"` and title; skips duplicates.
- **Precision Extraction**: Strips web boilerplate, retains tables, and preserves Arabic script without character encoding corruption.
- **Obsidian Frontmatter**: Writes notes formatted with standard `clippings` YAML tags (`title`, `source`, `author`, `published`, `created`, `description`, `tags`, `gdelt_tier`, `gdelt_topic_focus`, `gdelt_tone`, `gdelt_locations`).

#### Step 3: Archive Processed JSON Feed
Once extraction completes successfully, move the JSON file from `news/` to `news/archived/`:
```bash
mkdir -p news/archived
mv news/gdelt_sudan_<date>_<timestamp>.json news/archived/
```

---

## Configuration & Authentication

The BigQuery harvester connects using standard Google Cloud Application Default Credentials (ADC) or environment variables configured in `.env`:
- `GCP_PROJECT_ID=your-project-id` (required by BigQuery for billing/quota tracking, even for public datasets).
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json` (optional if using service account keys).
- Alternatively, authenticate the local environment using:
  ```bash
  gcloud auth application-default login
  ```
- **Cost & Quota Safeguard**: The query scans strictly 1 single daily partition (`_PARTITIONDATE = ...`), consuming ~2.5–4.5 GB per query. Under GCP's **1 TB/month free tier**, this is 100% free of charge.

---

## Downstream Pipeline Handoff

Once new raw articles are saved in [`raw/articles/`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/raw/articles/), proceed with the vault's two-phase ingestion workflow:
1. **Scope and Draft**:
   ```
   /ingest raw/articles/<newly-downloaded-article>.md
   ```
   Creates a draft source note in `wiki/sources/<source-slug>.md` (`status: "draft"`).
2. **Review & Compile**:
   Upon human approval (`status: "approved"`), compile into canonical nodes (`wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/citations/`) and synchronize ArcadeDB via `bash scripts/sync_vault_graph.sh`.
