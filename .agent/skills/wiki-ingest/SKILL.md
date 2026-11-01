---
name: wiki-ingest
description: Two-phase ingestion pipeline that (Phase 1) distills multilingual news, social media, transcripts, PDFs, satellite reports, and videos from raw/ into a reviewable draft source note (status draft) in wiki/sources/, and (Phase 2) compiles approved source notes (status approved) into wiki/ entities (events, actors [including quoted persons and media_source outlets], locations, themes, timelines, and standalone citations in wiki/citations/) and updates the ArcadeDB and ki graph databases.
---

# Wiki Ingest Skill (`wiki-ingest`)

## Objective
Operate a **two-phase, human-reviewed ingestion pipeline** for primary evidence in `raw/` (`raw/articles/`, `raw/social/`, `raw/videos/`, `raw/transcripts/`, `raw/reports/`, `raw/satellite/`):
- **Phase 1 — Source Distillation & Scoping (`status: "draft"`)**: Parse the raw artifact, execute `wiki-scope` (including 48-hour Spatio-Temporal Event Deduplication, mandatory `source_outlet` scoping as `Actor: media_source`, quoted speaker scoping as `Actor: person` with `role_title` and `affiliated_organization`, and verbatim quote scoping as standalone `Citation` entities in `wiki/citations/`), and create `wiki/sources/<source-slug>.md` with `status: "draft"` and `compiled: false`. Halt for user review.
- **Phase 2 — Approved Entity Compilation & Database Sync (`status: "approved"`)**: Once `status` is set to `"approved"`, compile and refactor the planned notes across `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, and `wiki/citations/`, generate the audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md`, update `wiki/index.md`, `wiki/overview.md`, and `wiki/glossary.md`, set `compiled: true`, and synchronize the `ki` index and ArcadeDB (`news`) database.

---

## Invocation Modes & Automatic Phase Routing

| Invocation Command | Target Argument | Executed Phase |
| :--- | :--- | :--- |
| `/ingest raw/<category>/<file>` | File in `raw/` or `_input/research/` | **Phase 1**: Creates `wiki/sources/<source-slug>.md` with `status: "draft"`, `compiled: false`, and **halts** for review. |
| `/ingest wiki/sources/<source-slug>.md` | Existing note in `wiki/sources/` | **Phase 2**: Verifies `status: "approved"` and `compiled: false`, compiles `wiki/` entities (including `wiki/citations/`, `person` actors, and `media_source` outlet), updates ledgers, and syncs ArcadeDB & `ki`. |
| `/ingest --approved` | Batch flag | **Phase 2 (Batch)**: Scans `wiki/sources/*.md` for all notes with `status: "approved"` and `compiled: false`, and executes Phase 2 for each. |

---

## Phase 1: Source Distillation & Scoping (`status: "draft"`)

### Step 1.1: Path & Immutability Verification
- Confirm the target file exists in `raw/` (or `_input/research/`).
- Never modify, rename, or delete any primary evidence file in `raw/`.

### Step 1.2: Pre-Ingestion Scoping & Event Deduplication (`wiki-scope`)
- Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
- Run the `wiki-scope` protocol:
  - Execute the **48-Hour Spatio-Temporal Event Deduplication Check** ($\lvert \Delta t_{\text{valid}} \rvert \le 48\text{ hours}$ at the same location).
  - Scope the publishing **`source_outlet`** (e.g., `[[UN News]]`) as an `Actor` (`subtype: "media_source"`).
  - Scope every **named speaker or eyewitness** quoted in Section 3 as an `Actor` (`subtype: "person"`) with `role_title` and `affiliated_organization`.
  - Scope every **key verbatim statement or eyewitness testimony** in Section 3 into `citations_to_create` (`wiki/citations/`).
  - **Mandatory Monthly Chronicle & Campaign/Thematic Timeline Rule**: For every calendar month `YYYY-MM` covered by candidate events in the source, check whether `[[YYYY-MM Sudan Conflict Chronicle]]` exists in `wiki/timelines/`. If it does not exist, add `[[YYYY-MM Sudan Conflict Chronicle]]` (`subtype: "monthly_chronicle"`) to `timelines_to_create`; if it already exists, add it to `nodes_to_refactor`. Also scope any longitudinal `campaign_timeline`, `thematic_timeline`, or `diplomatic_timeline`.
  - Separate candidates into `events_to_create` ($E$), `actors_to_create` ($A$), `locations_to_create` ($L$), `themes_to_create` ($T$), `timelines_to_create` ($TL$), `citations_to_create` ($C$), and `nodes_to_refactor` ($K$).

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
language: "en"          # Options: ar | en | fr | de
published_date: YYYY-MM-DD
ingested_date: YYYY-MM-DD
last_updated: YYYY-MM-DD
alignment: "international_org" # Options: independent | pro_saf | pro_rsf | state_media | civil_society_err | international_org | osint_verified
admiralty_source_reliability: "A"
admiralty_info_credibility: 2
admiralty_rating: "A2"
reliability_score: 0.90
events_to_create:
  - "[[YYYY-MM-DD Canonical Event Title]]"
actors_to_create:
  - "[[Outlet Name]]"
  - "[[Organization Name]]"
  - "[[Quoted Person Name]]"
locations_to_create: []
themes_to_create: []
timelines_to_create:
  - "[[YYYY-MM Sudan Conflict Chronicle]]"
citations_to_create:
  - "[[YYYY-MM-DD Quoted Person Name Statement Topic]]"
nodes_to_refactor: []
tags: [sudan, source-draft]
sources: ["raw/articles/example.md"]
aliases: ["Original Headline"]
---
```

Include five mandatory sections in `wiki/sources/<source-slug>.md`:
1. `## 1. 5W1H Source Intelligence Summary & Provenance` (including `> [!NOTE] Source Provenance & Admiralty Assessment` callout linking to `source_outlet`)
2. `## 2. Atomic Extracted Claims Table` (Claim ID, Atomic Claim, 5W1H Tuple, Modality [`confirmed | probable | alleged | denied | debunked`], Target Wiki Node)
3. `## 3. Bilingual Direct Citations & Forensic Evidence` (preserving both English translation and original Arabic/foreign script in blockquotes, and explicitly linking each blockquote to its `[[Speaker Person Actor]]`, their `[[Affiliated Organization]]`, and its standalone `[[Citation Entity]]` in `wiki/citations/`)
4. `## 4. Scoped Ingestion Plan (Pending Approval)` (listing Candidate New Events, Actors [Forces, Organizations, `source_outlet`, and `person` speakers], Locations, Themes, Timelines [`monthly_chronicle`, `campaign_timeline`, `thematic_timeline`], Standalone Citations, and Existing Nodes to Refactor)
5. `## 5. Related Primitives`

### Step 1.4: Log & Halt for Review
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest-draft | <source-slug> | Created draft source note in wiki/sources/<source-slug>.md (status: draft) with scoped manifest (E events, A actors, L locations, T themes, TL timelines, C citations, K refactors); awaiting approval.`
- **STOP**: Do NOT create or modify any notes in `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/citations/`, or `wiki/ingestions/`. Do NOT update `wiki/index.md` or `wiki/overview.md`, and do NOT run `ingest_to_arcadedb.py` or `sync_vault_graph.sh`.
- Inform the user that `wiki/sources/<source-slug>.md` is ready for review in `status: "draft"`.

---

## Phase 2: Approved Entity Compilation & Database Sync (`status: "approved"`)

### Step 2.1: Approval & State Verification
- Read `wiki/sources/<source-slug>.md` (or scan all `wiki/sources/*.md` if invoked with `--approved`).
- Verify `status: "approved"` and `compiled: false`.
- Read the approved target arrays (`events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `timelines_to_create`, `citations_to_create`, `nodes_to_refactor`) and Section 2/3 from `wiki/sources/<source-slug>.md`.

### Step 2.2: Multi-Node Compilation & Dual-Flow CoT Enforcement

#### Universal Formatting & Link Invariants (Axioms 4 & 7)
- **Zero ASCII Box Art**: Use GFM tables, Mermaid diagrams, and Obsidian callouts (`> [!NOTE]`).
- **Clean Wikilink Invariant**: Never wrap wikilinks in inline code backticks (`` `[[...]]` ``).
- **Table Pipe Invariant**: Escape any internal pipe inside a wikilink in a GFM table as `\|` (e.g., `| [[Target\|Alias]] |`) or use unaliased `[[Target]]`.
- **Shortest Canonical Wikilink Invariant**: Link to events, actors, locations, themes, timelines, and citations using direct titles (`[[El Fasher]]`, `[[Volker Türk]]`, `[[2026-10 Sudan Conflict Chronicle]]`, `[[2026-10-23 Volker Türk Condemnation of Sudan Drone Escalation and Arms Influx]]`), NEVER with directory prefixes. Link to sources as `[[sources/<source-slug>]]`.
- **Mermaid Clean Label Invariant**: Never place `[[...]]` or unquoted special characters (`:&()`) inside Mermaid node labels.

#### Ingest-Time Dual-Flow CoT Section Arcs (Axiom 9)
Structure every newly created or refactored note according to its canonical epistemic arc:
1. **Event Notes (`wiki/events/`, `type: event`, `subtype: incident | campaign | crisis | diplomatic`)**:
   - `## 1. Event Anchor & 5W1H Summary` (`EVENT_ANCHOR`)
   - `## 2. Chronological Sequence & Tactical Mechanics ("What & How")` (`CHRONOLOGICAL_MECHANICS`)
   - `## 3. Causal Drivers & Strategic Motives ("Why")` (`CAUSAL_MOTIVES`)
   - `## 4. Humanitarian, Territorial & Geopolitical Impact` (`IMPACT_ASSESSMENT`)
   - `## 5. Competing Narratives, Attribution & Contradictions` (`CONTRADICTION_MATRIX`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
2. **Actor Notes (`wiki/actors/`, `type: actor`, `subtype: state_force | armed_group | political_body | civil_society | person | media_source`)**:
   - For `subtype: "person"`, include `role_title` and `affiliated_organization` in frontmatter, link to their parent institution (`[[OHCHR]]`, `[[UNISFA]]`, etc.), and link to their standalone `[[Citation]]` notes in Section 5.
   - For `subtype: "media_source"`, include `parent_organization`, `editorial_alignment`, `baseline_admiralty_reliability`, and `url` in frontmatter, and log published `[[sources/...]]` notes in Section 5.
   - `## 1. Identity, Classification & Leadership Anchor` (`ACTOR_ANCHOR`)
   - `## 2. Historical Lineage, Factions & Command Structure` (`COMMAND_LINEAGE`)
   - `## 3. Strategic Objectives, Ideology & Political Economy ("Why")` (`STRATEGIC_DOCTRINE`)
   - `## 4. Operational Capabilities, Alliances & Foreign Backing` (`ALLIANCE_NETWORK`)
   - `## 5. Chronological Event Footprint & Accountability Record` (`EVENT_FOOTPRINT`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
3. **Location Notes (`wiki/locations/`, `type: location`)**:
   - `## 1. Geopolitical Identity & Strategic Significance` (`LOCATION_ANCHOR`)
   - `## 2. Territorial Control History & Armed Presence` (`TERRITORIAL_CONTROL`)
   - `## 3. Key Infrastructure, Trade Corridors & Resources` (`INFRASTRUCTURE_LOGISTICS`)
   - `## 4. Humanitarian Status, Displacement & Civil Services` (`HUMANITARIAN_STATUS`)
   - `## 5. Chronological Log of Major Conflict Events` (`EVENT_LOG`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
4. **Theme Notes (`wiki/themes/`, `type: theme`)**:
   - `## 1. Core Thesis & Structural Mechanism ("Why")` (`DEFINITIONAL_ANCHOR`)
   - `## 2. Historical Roots & Political Economy Anatomy` (`MECHANISTIC_DEEPEN`)
   - `## 3. Operational Manifestations Across Frontlines` (`MANIFESTATION_TRAP`)
   - `## 4. Humanitarian, Regional & Diplomatic Consequences` (`IMPACT_ASSESSMENT`)
   - `## 5. Empirical Debates, Uncertainties & Competing Analyses` (`EMPIRICAL_BOUNDARY`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
5. **Timeline Notes (`wiki/timelines/`, `type: timeline`, `subtype: monthly_chronicle | campaign_timeline | thematic_timeline | diplomatic_timeline`)**:
   - Include `start_date`, `end_date`, `time_horizon`, `theatres_covered`, `events_chronicled`, `citations_chronicled`, `actors_involved`, `themes_linked`, `cumulative_fatalities_low`, `cumulative_fatalities_best`, `cumulative_fatalities_high`, and `admiralty_rating` in frontmatter.
   - `## 1. Temporal Scope, Theatre Coverage & Strategic Periodization` (`TIMELINE_ANCHOR`)
   - `## 2. Chronological Event & Citation Ledger (Bitemporal Sequence)` (`CHRONOLOGICAL_LEDGER`)
   - `## 3. Causal Escalation Chains, Turning Points & Tempo Analysis` (`CAUSAL_ESCALATION`)
   - `## 4. Cumulative Humanitarian, Territorial & Attribution Telemetry` (`CUMULATIVE_TELEMETRY`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)
6. **Citation Notes (`wiki/citations/`, `type: citation`, `subtype: official_statement | eyewitness_testimony | military_communique | forensic_finding | diplomatic_resolution`)**:
   - Lead Callout: `> [!QUOTE] Forensic Citation Anchor` (Speaker, Role, Affiliated Organization, Date, Originating Source & Outlet, Speech Act, Admiralty Rating).
   - `## 1. Speaker Provenance, Institutional Role & Context` (`CITATION_ANCHOR`)
   - `## 2. Verbatim Bilingual Citation & Forensic Text` (`VERBATIM_EVIDENCE`)
   - `## 3. Substantive Claims, Event Grounding & Contradiction Impact` (`FORENSIC_GROUNDING`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`)

### Step 2.3: Ingestion Dossier & Source Finalization
- Author a standalone audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` (`type: "ingestion"`), listing `events_created`, `actors_created`, `locations_created`, `themes_created`, `timelines_created`, `citations_created`, `nodes_refactored`, and `contradictions_logged`.
- **Mandatory Contradiction Synchronization Invariant**: If `contradictions_logged` is populated in the ingestion dossier (e.g. `[ATTRIBUTION_CONFLICT]`, `[MAGNITUDE_DISCREPANCY]`, `[TARGET_FRAMING_CONFLICT]`), the corresponding newly compiled or refactored Event note(s) in `wiki/events/` MUST have their frontmatter `contradiction_flags` synchronized with these exact flags, and Section 5 of the Event note must provide a side-by-side Claim Comparison Matrix documenting the competing perspectives.
- Update `wiki/sources/<source-slug>.md` frontmatter to `compiled: true` and `compiled_at: YYYY-MM-DD`.

### Step 2.4: Batch Catalog, Ledger & Graph Database Synchronization
- Register new actors (including quoted `person` actors and `media_source` outlets), locations (with P-Codes), and Arabic/English aliases in `wiki/glossary.md`.
- Add the approved source note, timeline notes, standalone citation notes, and all newly created domain notes with 1-line summaries to `wiki/index.md`.
- Update `wiki/overview.md` (Living SITREP) if territorial control, humanitarian indicators, or major narrative contradictions shifted.
- Synchronize the `ki` index and ArcadeDB (`news`) multi-model graph database via `./scripts/sync_vault_graph.sh` and `python3 scripts/ingest_to_arcadedb.py`, and verify `ki status -v -C wiki` reports `✓ READY`.
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest-compile | <source-slug> | Compiled approved source into N notes (E events, A actors, L locations, T themes, TL timelines, C citations, K refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index, SITREP & glossary; synced ki & ArcadeDB.`
