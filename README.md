# Sovereign LLM-Wiki (`llm-wiki-news`)

A local-first, autonomous Sudan Conflict & OSINT knowledge compiler and Socratic intelligence studio powered by:
- **Obsidian IDE**: Agent-managed markdown knowledge graph (`wiki/`).
- **ArcadeDB (`arcadedb-news`)**: Sovereign multi-model graph and vector storage (`http://localhost:2481`).
- **FastMCP (`fastmcp-news`)**: Semantic routing and Dual-Flow Chain-of-Thought (CoT) middleware (`http://localhost:8001`).
- **Chainlit (`chainlit-news`)**: Socratic Learning Studio with live streaming (`http://localhost:8081`).
- **Astro 5**: High-speed digital garden with Pagefind and interactive Mermaid diagrams (`http://localhost:4322`).

---

## Directory Topography

- `raw/`: Immutable multilingual primary evidence repository (READ-ONLY).
  - `raw/articles/`: Extracted news articles in Arabic, English, French, etc.
  - `raw/social/`: Archived Telegram communiqués, X threads, Facebook posts.
  - `raw/videos/`: Field footage and video recordings.
  - `raw/transcripts/`: Bilingual audio/video transcripts with timestamped citations.
  - `raw/reports/`: UN OCHA, IPC, ACLED, and human rights investigation dossiers.
  - `raw/satellite/`: Remote sensing reports (Yale HRL, Sudan Witness).
- `news/`: Operational feed JSON staging directory.
  - `news/archived/`: Historical feed JSON archives processed by the ingestion pipeline.
- `wiki/`: Compiled Sudan News & OSINT Knowledge Graph (READ-WRITE).
  - `wiki/events/`: Discrete conflict/news incidents, military campaigns, and diplomatic developments.
  - `wiki/actors/`: Belligerents, political bodies, civil society, quoted persons, and media outlets.
  - `wiki/locations/`: Geopolitical nodes anchored to UN OCHA Sudan P-Codes (`ADM1`–`ADM4`).
  - `wiki/themes/`: Enduring structural conflict drivers, war economy mechanics, and military doctrines.
  - `wiki/timelines/`: Monthly chronicles and thematic chronological ledgers.
  - `wiki/citations/`: Verbatim bilingual citations, official communiqués, and eyewitness testimonies.
  - `wiki/sources/`: Per-artifact source distillations with NATO Admiralty ratings (`A1`–`F6`).
- `scripts/`: Data collection, BigQuery harvesting, text extraction, database sync, and verification tooling.
- `_input/`: Operational workspace for active tasks, research dossiers, and Kanban project trackers.

---

## News & OSINT Harvesting Scripts

The repository includes automated harvesting and extraction pipelines for continuous conflict intelligence monitoring.

### 1. Radio Dabanga Arabic Harvester (`scripts/fetch_dabanga_arabic.py`)

Scrapes Radio Dabanga's Arabic portal (`dabangasudan.org/ar/`) for a specified date range, normalizes pagination, excludes radio/TV broadcast media, and extracts full-text news articles into `raw/articles/`.

#### Key Capabilities
- **Date Normalization**: Automatically re-orders inverted dates (e.g., `2026-11-02+2026-11-01` $\to$ `2026-11-01+2026-11-02`) required by WordPress Search & Filter.
- **Multi-Page Pagination**: Traverses pagination pages (`/ar/page/2?post_date=...`) to collect all articles in the window.
- **Audio/Video Broadcast Filtering**: Automatically detects and excludes radio broadcasts, TV programs, and podcast stubs (e.g., *Sudan This Week*, *Sudan Now+*, *Daily Bulletin*) using HTML5 `<audio>` / `<video>` detection, `.mp3` / `.mp4` URLs, embedded players (YouTube/Vimeo), and low word-count thresholds (< 60 words). **Only full written news articles are retained**.
- **Automated Extraction & Archival**: Directly invokes `extract_articles_trafilatura.py` to save clean Markdown files in `raw/articles/` and moves the feed JSON to `news/archived/`.

#### Usage Examples

```bash
# 1. Harvest and extract using a Dabanga date filter URL
python3 scripts/fetch_dabanga_arabic.py --url "https://www.dabangasudan.org/ar/?post_date=2026-11-02+2026-11-01"

# 2. Harvest using explicit start and end dates
python3 scripts/fetch_dabanga_arabic.py --start-date 2026-11-01 --end-date 2026-11-02

# 3. Dry-run / URL harvest only without downloading full articles
python3 scripts/fetch_dabanga_arabic.py --no-extract --start-date 2026-11-01 --end-date 2026-11-02

# 4. Include broadcast/audio programs if specifically needed
python3 scripts/fetch_dabanga_arabic.py --include-broadcasts
```

---

### 2. GDELT BigQuery Harvester (`scripts/fetch_gdelt_bigquery.py`)

Extracts Sudan conflict news from GDELT 2.0 Global Knowledge Graph (`gdelt-bq.gdeltv2.gkg_partitioned`) using Google Cloud BigQuery.

#### Key Capabilities
- **Verified Publisher Matrix**: Filters against Tier 1 International (BBC, Reuters, AP, AFP, Al Jazeera, DW, Guardian), Tier 2 Regional (Asharq, Al Arabiya, The National), and Field outlets (Radio Dabanga, Sudan Tribune, Ayin Network).
- **Translingual Arabic Support**: Ingests Arabic reporting via GDELT `TranslationInfo` (`srclc:ara`) and URL structure.
- **Parallel URL Validation**: Verifies candidate URLs in parallel (`HTTP 200 OK`) and handles Cloudflare WAF protection.
- **Clean JSON Export**: Outputs verified feeds to `news/` for downstream Trafilatura extraction.

#### Usage Examples

```bash
# Fetch news from yesterday (relative partition)
python3 scripts/fetch_gdelt_bigquery.py --days-ago 1

# Fetch news from 5 days ago with custom limit
python3 scripts/fetch_gdelt_bigquery.py --days-ago 5 --limit 200

# Fetch news for a specific calendar date
python3 scripts/fetch_gdelt_bigquery.py --date 2026-11-01
```

---

### 3. Trafilatura Article Extractor (`scripts/extract_articles_trafilatura.py`)

Downloads and extracts full-text news articles from feed JSON files generated by GDELT or Dabanga harvesters.

#### Key Capabilities
- **Precision Extraction**: Uses Trafilatura to extract article text, headlines, authors, and publish dates while removing navigation, boilerplate, and ads.
- **Deduplication Sentinel**: Checks existing URLs and normalized article titles in `raw/articles/` before fetching, preventing duplicate evidence files.
- **Obsidian Frontmatter**: Generates clean YAML frontmatter (`title`, `source`, `published_date`, `retrieved_at`, `language`, `publisher`, `tier`, `locations`, `topic_focus`).

#### Usage Examples

```bash
# Extract articles from a specific feed JSON
python3 scripts/extract_articles_trafilatura.py --input news/gdelt_sudan_dminus1_20261102_062700.json

# Process the latest feed JSON in news/ with a batch limit
python3 scripts/extract_articles_trafilatura.py --max-articles 30
```

---

### 4. Daily News Orchestrator (`scripts/harvest_daily_news.py`)

Unified orchestrator that executes BigQuery harvesting, runs Trafilatura extraction, and archives the processed feed JSON in a single step.

```bash
# Harvest and extract today's news
python3 scripts/harvest_daily_news.py

# Harvest and extract news from 2 days ago
python3 scripts/harvest_daily_news.py --days-ago 2
```

---

### 5. Knowledge Graph Linter (`scripts/lint_vault.py`)

Enforces graph consistency, Dual-Flow CoT micro/macro invariants, table pipe escaping (`\|`), clean wikilinks, and NATO Admiralty rating adherence.

```bash
# Run comprehensive vault audit with Chain-of-Thought checks
python3 scripts/lint_vault.py --cot
```

---

## Service & Port Topology (Side-by-Side Isolation)

Configured with isolated containers, volumes, and network (`wiki-news-net`) to run side-by-side with other LLM-Wiki instances:

| Service | Container Name | Host Port Mapping | Local Endpoint |
| :--- | :--- | :--- | :--- |
| **ArcadeDB Studio / REST / MCP** | `arcadedb-news` | `2481:2480`, `2425:2424` | `http://localhost:2481` |
| **FastMCP Middleware** | `fastmcp-news` | `8001:8000` | `http://localhost:8001` |
| **Chainlit Learning Studio** | `chainlit-news` | `8081:8080` | `http://localhost:8081` |
| **Astro Digital Garden** | *(Host Dev Server)* | `4322` | `http://localhost:4322` |

---

## Quick Start

1. **Check Prerequisites**:
   ```bash
   ./scripts/check_prerequisites.sh
   ```
2. **Configure Environment**:
   ```bash
   cp setup/.env.example .env
   # Add GCP_PROJECT_ID=<your-gcp-project> for BigQuery access
   ```
3. **Install Dependencies**:
   ```bash
   uv sync
   npm --prefix site install
   ```
4. **Authenticate Google BigQuery (for GDELT extraction)**:
   ```bash
   gcloud auth application-default login
   gcloud auth application-default set-quota-project <your-gcp-project-id>
   ```
5. **Harvest Primary Evidence**:
   ```bash
   # Radio Dabanga Arabic articles
   python3 scripts/fetch_dabanga_arabic.py --url "https://www.dabangasudan.org/ar/?post_date=2026-11-02+2026-11-01"

   # GDELT 2.0 BigQuery articles
   python3 scripts/harvest_daily_news.py --days-ago 1
   ```
6. **Start ArcadeDB (`arcadedb-news`) & Bootstrap Schema**:
   ```bash
   podman compose -f setup/compose.arcadedb.yaml up -d --no-build
   uv run scripts/bootstrap_arcadedb.py
   ```
7. **Start Astro Frontend & Chainlit Studio**:
   ```bash
   npm --prefix site run dev
   podman compose -f setup/compose.chainlit.yaml up -d --no-build
   ```

See `setup/boilerplate_architecture_and_clean_clone_guide.md` for comprehensive documentation.
