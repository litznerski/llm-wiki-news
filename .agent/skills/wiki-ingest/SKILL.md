---
name: wiki-ingest
description: Two-phase ingestion pipeline that (Phase 1) distills multilingual news, social media, transcripts, PDFs, satellite reports, and videos from raw/ into a reviewable draft source note (status draft) in wiki/sources/, and (Phase 2) compiles approved source notes (status approved) into wiki/ entities (events, actors, locations, themes, timelines) and updates the ArcadeDB and ki graph databases.
---

# Wiki Ingest Skill (`wiki-ingest`)

## Objective
Operate a **two-phase, human-reviewed ingestion pipeline** for primary evidence in `raw/` (`raw/articles/`, `raw/social/`, `raw/videos/`, `raw/transcripts/`, `raw/reports/`, `raw/satellite/`):
- **Phase 1 — Source Distillation & Scoping (`status: "draft"`)**: Parse the raw artifact, execute `wiki-scope` (including the 48-hour Spatio-Temporal Event Deduplication check), and create `wiki/sources/<source-slug>.md` with `status: "draft"` and `compiled: false`, embedding the NATO Admiralty rating (`A1`–`F6`), Atomic Extracted Claims Table, Bilingual Direct Citations, and the **Scoped Ingestion Plan**. Halt for user review.
- **Phase 2 — Approved Entity Compilation & Database Sync (`status: "approved"`)**: Once `status` is set to `"approved"`, compile and refactor the planned notes across `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, and `wiki/timelines/`, generate the audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md`, update `wiki/index.md`, `wiki/overview.md`, and `wiki/glossary.md`, set `compiled: true`, and synchronize the `ki` index and ArcadeDB (`news`) database.

---

## Invocation Modes & Automatic Phase Routing

| Invocation Command | Target Argument | Executed Phase |
| :--- | :--- | :--- |
| `/ingest raw/<category>/<file>` | File in `raw/` or `_input/research/` | **Phase 1**: Creates `wiki/sources/<source-slug>.md` with `status: "draft"`, `compiled: false`, and **halts** for review. |
| `/ingest wiki/sources/<source-slug>.md` | Existing note in `wiki/sources/` | **Phase 2**: Verifies `status: "approved"` and `compiled: false`, compiles `wiki/` entities, updates ledgers, and syncs ArcadeDB & `ki`. (If `status: "draft"`, halts with a prompt to set `status: "approved"`). |
| `/ingest --approved` | Batch flag | **Phase 2 (Batch)**: Scans `wiki/sources/*.md` for all notes with `status: "approved"` and `compiled: false`, and executes Phase 2 for each. |

---

## Supported Source Types & Parsing Procedures

1. **News Articles & Social Media Artefacts (`raw/articles/`, `raw/social/`, `_input/research/`)**: Read directly via `view_file`. Preserve publication timestamps, author/channel handles, and URLs.
2. **PDF Reports & Satellite Dossiers (`raw/reports/`, `raw/satellite/`)**: View directly via `view_file` (or extract text via `pypdf` for large multi-page documents). Record imagery acquisition dates, coordinates, and thermal/crater findings.
3. **Spoken Transcripts (`raw/transcripts/`)**: Read full transcript directly and preserve temporal timestamps (e.g., `[04:15]`) in citations.
4. **Direct Multimodal Video Files (`raw/videos/`)**:
   - **File size < 100 MB**: Ingest directly using `view_file`. Analyze spoken audio, uniform insignias, vehicle markings, weapon systems, and visible landmarks.
   - **File size ≥ 100 MB**: Advise the user to provide or extract the transcript in `raw/transcripts/<slug>.md`.

---

## Phase 1: Source Distillation & Scoping (`status: "draft"`)

### Step 1.1: Path & Immutability Verification
- Confirm the target file exists in `raw/` (or `_input/research/`).
- Never modify, rename, or delete any primary evidence file in `raw/`.

### Step 1.2: Pre-Ingestion Scoping & Event Deduplication (`wiki-scope`)
- Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
- Run the `wiki-scope` protocol:
  - Execute the **48-Hour Spatio-Temporal Event Deduplication Check** ($\lvert \Delta t_{\text{valid}} \rvert \le 48\text{ hours}$ at the same location).
  - Apply the **$\ge 0.70$ News & OSINT Significance Filter**.
  - Cross-reference `wiki/glossary.md` to map Arabic script, Sudanese kunyas (e.g., *Hemedti / حميدتي* $\to$ `[[Mohamed Hamdan Dagalo]]`), and UN OCHA P-Codes (`SD01`–`SD18`) to canonical English titles.
  - Separate candidates into `events_to_create` ($E$), `actors_to_create` ($A$), `locations_to_create` ($L$), `themes_to_create` ($T$), and `nodes_to_refactor` ($K$).

### Step 1.3: Draft Source Note Creation (`wiki/sources/<source-slug>.md`)
Author `wiki/sources/<source-slug>.md` with `status: "draft"` and `compiled: false`:

```yaml
---
title: "YYYY-MM-DD Outlet: Canonical Source Title"
type: "source"
subtype: "news_article" # Options: news_article | social_post | video_osint | satellite_report | official_communique | ngo_report | eyewitness
status: "draft"         # Options: draft | approved
compiled: false         # Flipped to true after Phase 2 completes
compiled_at: null       # Populated with YYYY-MM-DD upon Phase 2 completion
source_outlet: "[[Outlet Name]]"
raw_file: "raw/articles/example.md"
language: "ar"          # Options: ar | en | fr | de
published_date: YYYY-MM-DD
ingested_date: YYYY-MM-DD
last_updated: YYYY-MM-DD
alignment: "independent" # Options: independent | pro_saf | pro_rsf | state_media | civil_society_err | international_org | osint_verified
admiralty_source_reliability: "B"
admiralty_info_credibility: 2
admiralty_rating: "B2"
reliability_score: 0.82
events_to_create:
  - "[[YYYY-MM-DD Canonical Event Title]]"
actors_to_create: []
locations_to_create: []
themes_to_create: []
nodes_to_refactor:
  - "[[Rapid Support Forces]]"
  - "[[El Fasher]]"
tags: [darfur, shelling, source-draft]
sources: ["raw/articles/example.md"]
aliases: ["Original Headline"]
---
```

Include five mandatory sections in `wiki/sources/<source-slug>.md`:
1. `## 1. 5W1H Source Intelligence Summary & Provenance` (including `> [!NOTE] Source Provenance & Admiralty Assessment` callout)
2. `## 2. Atomic Extracted Claims Table` (Claim ID, Atomic Claim, 5W1H Tuple, Modality [`confirmed | probable | alleged | denied | debunked`], Target Wiki Node)
3. `## 3. Bilingual Direct Citations & Forensic Evidence` (preserving both English translation and original Arabic/foreign script in blockquotes)
4. `## 4. Scoped Ingestion Plan (Pending Approval)` (listing Candidate New Events, Actors, Locations, Themes/Timelines, and Existing Nodes to Refactor)
5. `## 5. Related Primitives`

### Step 1.4: Log & Halt for Review
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest-draft | <source-slug> | Created draft source note in wiki/sources/<source-slug>.md (status: draft) with scoped manifest (E events, A actors, L locations, T themes, K refactors); awaiting approval.`
- **STOP**: Do NOT create or modify any notes in `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, or `wiki/ingestions/`. Do NOT update `wiki/index.md` or `wiki/overview.md`, and do NOT run `ingest_to_arcadedb.py` or `sync_vault_graph.sh`.
- Inform the user that `wiki/sources/<source-slug>.md` is ready for review in `status: "draft"`, and instruct them to change `status: "draft"` to `status: "approved"` and invoke `/ingest wiki/sources/<source-slug>.md` (or `/ingest --approved`) to run Phase 2.

---

## Phase 2: Approved Entity Compilation & Database Sync (`status: "approved"`)

### Step 2.1: Approval & State Verification
- Read `wiki/sources/<source-slug>.md` (or scan all `wiki/sources/*.md` if invoked with `--approved`).
- Verify `status: "approved"` and `compiled: false`:
  - If `status: "draft"`, abort and inform the user: *"Source `wiki/sources/<source-slug>.md` is still in `status: draft`. Please review the note and change `status: draft` to `status: approved` before running Phase 2."*
  - If `status: "approved"` and `compiled: true`, skip unless `--force` is specified.
- Read the approved target arrays (`events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `nodes_to_refactor`) and Section 2 (`## 2. Atomic Extracted Claims Table`) from `wiki/sources/<source-slug>.md`, respecting any edits made by the user during review.

### Step 2.2: Multi-Node Compilation & Dual-Flow CoT Enforcement

#### Universal Formatting & Link Invariants (Axioms 4 & 7)
- **Zero ASCII Box Art**: Use GFM tables, Mermaid diagrams, and Obsidian callouts (`> [!NOTE]`).
- **Clean Wikilink Invariant**: Never wrap wikilinks in inline code backticks (`` `[[...]]` ``).
- **Table Pipe Invariant**: Escape any internal pipe inside a wikilink in a GFM table as `\|` (e.g., `| [[Target\|Alias]] |`) or use unaliased `[[Target]]`.
- **Shortest Canonical Wikilink Invariant**: Link to events, actors, locations, themes, and timelines using direct titles (`[[El Fasher]]`, `[[Rapid Support Forces]]`), NEVER `[[wiki/locations/El Fasher]]`. Link to sources as `[[sources/<source-slug>]]`.
- **Mermaid Clean Label Invariant**: Never place `[[...]]` or unquoted special characters (`:&()`) inside Mermaid node labels.

#### Ingest-Time Dual-Flow CoT Section Arcs (Axiom 9)
Structure every newly created or refactored note according to its canonical 6-stage epistemic arc:
1. **Event Notes (`wiki/events/`, `type: event`, `subtype: incident | campaign | crisis | diplomatic`)**:
   - Lead Callout: `> [!NOTE] 5W1H Event Intelligence Anchor`
   - `## 1. Event Anchor & 5W1H Summary` (`EVENT_ANCHOR`)
   - `## 2. Chronological Sequence & Tactical Mechanics ("What & How")` (`CHRONOLOGICAL_MECHANICS`)
   - `## 3. Causal Drivers & Strategic Motives ("Why")` (`CAUSAL_MOTIVES`)
   - `## 4. Humanitarian, Territorial & Geopolitical Impact` (`IMPACT_ASSESSMENT`)
   - `## 5. Competing Narratives, Attribution & Contradictions` (`CONTRADICTION_MATRIX`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
2. **Actor Notes (`wiki/actors/`, `type: actor`, `subtype: state_force | armed_group | political_body | civil_society | person | media_source`)**:
   - `## 1. Identity, Classification & Leadership Anchor` (`ACTOR_ANCHOR`)
   - `## 2. Historical Lineage, Factions & Command Structure` (`COMMAND_LINEAGE`)
   - `## 3. Strategic Objectives, Ideology & Political Economy ("Why")` (`STRATEGIC_DOCTRINE`)
   - `## 4. Operational Capabilities, Alliances & Foreign Backing` (`ALLIANCE_NETWORK`)
   - `## 5. Chronological Event Footprint & Accountability Record` (`EVENT_FOOTPRINT`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
3. **Location Notes (`wiki/locations/`, `type: location`, `subtype: country | state_adm1 | locality_adm2 | city_town | neighborhood_site | idp_camp | infrastructure | border_crossing`)**:
   - `## 1. Geopolitical Identity & Strategic Significance` (`LOCATION_ANCHOR`)
   - `## 2. Territorial Control History & Armed Presence` (`TERRITORIAL_CONTROL`)
   - `## 3. Key Infrastructure, Trade Corridors & Resources` (`INFRASTRUCTURE_LOGISTICS`)
   - `## 4. Humanitarian Status, Displacement & Civil Services` (`HUMANITARIAN_STATUS`)
   - `## 5. Chronological Log of Major Conflict Events` (`EVENT_LOG`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
4. **Theme Notes (`wiki/themes/`, `type: theme`, `subtype: war_economy | humanitarian_driver | military_doctrine | political_dynamic | information_warfare`)**:
   - `## 1. Core Thesis & Structural Mechanism ("Why")` (`DEFINITIONAL_ANCHOR`)
   - `## 2. Historical Roots & Political Economy Anatomy` (`MECHANISTIC_DEEPEN`)
   - `## 3. Operational Manifestations Across Frontlines` (`MANIFESTATION_TRAP`)
   - `## 4. Humanitarian, Regional & Diplomatic Consequences` (`IMPACT_ASSESSMENT`)
   - `## 5. Empirical Debates, Uncertainties & Competing Analyses` (`EMPIRICAL_BOUNDARY`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)

### Step 2.3: Ingestion Dossier & Source Finalization
- Author a standalone audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` (`type: "ingestion"`), listing `events_created`, `actors_created`, `locations_created`, `themes_created`, `nodes_refactored`, and `contradictions_logged`.
- Update `wiki/sources/<source-slug>.md` frontmatter:
  - Set `compiled: true` and `compiled_at: YYYY-MM-DD`.
  - Replace `source-draft` tag (if present) with `source-compiled`.

### Step 2.4: Batch Catalog, Ledger & Graph Database Synchronization
- Register new actors, locations (with P-Codes), and Arabic/English aliases in `wiki/glossary.md`.
- Add the approved source note and all newly created domain notes with 1-line summaries to `wiki/index.md`.
- Update `wiki/overview.md` (Living SITREP) if territorial control, humanitarian indicators, or major narrative contradictions shifted.
- Synchronize the `ki` index and ArcadeDB (`news`) multi-model graph database:
  - Run `./scripts/sync_vault_graph.sh` (or `ki add -C wiki "<relative-path>"` + `python3 scripts/ingest_to_arcadedb.py`) and verify `ki status -v -C wiki` reports `✓ READY`.
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest-compile | <source-slug> | Compiled approved source into N notes (E events, A actors, L locations, T themes, K refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index, SITREP & glossary; synced ki & ArcadeDB.`
