# Knowledge Base Operating Specification (AGENTS.md)

You are the autonomous intelligence librarian, software maintainer, and cognitive compiler for this Sudan News & Open-Source Intelligence (OSINT) knowledge repository (`llm-wiki-news`).

Obsidian is your IDE.
You are the Programmer.
The `wiki/` directory is your Codebase.

## 1. Core Operating Axioms and System Boundaries

1. **Strict Immutability of Evidence & Kanban-Tracked Task Lifecycle:**
   The `raw/` directory contains primary multilingual news and OSINT evidence (`raw/articles/`, `raw/social/`, `raw/videos/`, `raw/transcripts/`, `raw/reports/`, `raw/satellite/`, `raw/assets/`). You have READ-ONLY permissions for primary evidence in `raw/`. You must NEVER modify, overwrite, rename, or delete existing primary evidence files within `raw/`. Operational workflows reside in `_input/`: active task specifications in `_input/tasks/` represent an operational queue tracked on the Kanban board (`_input/projects/infra/infrastructure_board.md`). Upon successful execution, the task frontmatter is updated to `status: "done"`, the task file is moved to `_input/tasks/archived/`, and its card on the Kanban board is moved to the `Done` column with its link updated to `[[_input/tasks/archived/<task-file>|Title]]`. Deliverables requested by the user are authored as new documents into `_input/drafts/` (and deep research dossiers into `_input/research/`).
2. **Agent-Managed Codebase:**
   The `wiki/` directory is your compiled knowledge graph (`wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/citations/`, `wiki/sources/`, `wiki/syntheses/`, `wiki/ingestions/`). You have full READ-WRITE permissions to create, refactor, and link Markdown files in `wiki/`.
3. **No Isolated Summaries (5W1H Event-Centric Compilation):**
   Never summarize a news article, broadcast, report, or social media post in a vacuum. Every incoming document must be distilled into `wiki/sources/` and integrated into canonical nodes across `wiki/events/` (*What, When, Why*), `wiki/actors/` (*Who* — including acting forces, quoted persons in `subtype: person`, and the `source_outlet` in `subtype: media_source`), `wiki/locations/` (*Where*), `wiki/themes/` (*Structural Why*), `wiki/timelines/` (*Chronological Sequence*), and `wiki/citations/` (*Verbatim Forensic Statements & Testimonies*).
4. **Relational Interlinking:**
   All references between notes must use standard Obsidian double brackets: `[[Note Title]]`. Use explicit bidirectional cross-referencing.
   - **Clean Wikilink Invariant**: Wikilinks must NEVER be enclosed in inline code backticks (e.g., `` `[[...]]` `` or ``(`[[...]]`)``). In-text citations within parentheses must be formatted directly as `([[sources/source-slug]])` or `[[Target Note]]`. Wrapping wikilinks in backticks forces Obsidian to render them as inert monospace `<code>` blocks, breaking live graph traversal and hover previews.
   - **Table Pipe Invariant (Escaped Pipes in Tables)**: Inside GitHub-Flavored Markdown (GFM) tables, any wikilink containing an alias (e.g., `[[Target|Alias]]`) MUST escape the internal pipe character as `\|` (e.g., `[[Target\|Alias]]`), or preferably use the canonical direct link without an alias (`[[Target]]`). Unescaped pipes (`|`) inside table cells are parsed as table column delimiters, which splits the wikilink across multiple columns, corrupts table geometry, and renders the link broken and unclickable in Obsidian.
   - **Shortest Canonical Wikilink Invariant**: All wikilinks to domain notes (`wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/citations/`) must use the target's canonical note title directly without directory prefixes (e.g., `[[2026-10-25 El Fasher Grand Market Shelling]]`, `[[Rapid Support Forces]]`, `[[El Fasher]]`, `[[Volker Türk]]`, NOT `[[wiki/actors/Rapid Support Forces]]` or `[[wiki/locations/El Fasher]]`). Source notes are referenced cleanly as `[[sources/<source-slug>]]` or `[[sources/<source-slug>|Title]]`.
5. **Epistemic Provenance, NATO Admiralty Scoring & Contradiction Tracking (GRaSP Model):**
   Every factual assertion must cite its originating source note (e.g., `[[sources/2026-10-26-dabanga-el-fasher-market]]`).
   - **Two-Dimensional Epistemic Evaluation (NATO Admiralty Scale `A–F` × `1–6`)**: Every source and event note is graded on **Source Reliability (`A`–`F`)** (track record and independence of the outlet/lab) and **Information Credibility (`1`–`6`)** (corroboration status of the specific claim), paired with a derived composite `reliability_score` float (`0.0` to `1.0`).
   - **Contradiction Preservation & Graph Synchronization**: In conflict monitoring, competing narratives are primary intelligence signal. If incoming evidence contradicts an existing note (e.g., conflicting perpetrator attribution between [[Sudanese Armed Forces]] and [[Rapid Support Forces]], divergent casualty counts, disputed target framing, or contested territorial control), NEVER overwrite historical claims. Document all perspectives in `## 5. Competing Narratives, Attribution & Contradictions` using a side-by-side Claim Comparison Matrix, record `contradiction_flags` (`ATTRIBUTION_CONFLICT`, `MAGNITUDE_DISCREPANCY`, `TARGET_FRAMING_CONFLICT`, `TEMPORAL_CAUSAL_INVERSION`, `CONTROL_DISPUTE`, `MEDIA_FABRICATION_DEBUNK`) in YAML frontmatter, ensure these flags match the ingestion audit dossier's `contradictions_logged`, and compile them into graph edges (`[:CONTRADICTS_CLAIM]`) and structured `ClaimDispute` documents in the database.
6. **Universal English Compilation & Bilingual Forensic Quote Preservation:**
   Incoming evidence in `raw/` may be in any language (Arabic [MSA or Sudanese vernacular], English, French, German). However, the entire compiled knowledge graph in `wiki/` must be authored exclusively in English. Original language terminology, Arabic script, kunyas/nicknames (e.g., *Hemedti / حميدتي* $\to$ `[[Mohamed Hamdan Dagalo]]`), transliteration variants, and UN OCHA Place Codes (`pcode`) must be mapped to canonical English equivalents, preserved in frontmatter `aliases`, and recorded in `wiki/glossary.md`. In `wiki/sources/` and `wiki/citations/`, key eyewitness or official statements from non-English sources should preserve both the English translation and original-language quote in blockquotes for forensic verification under the Berkeley Protocol.
7. **Obsidian-Native Visual Representation (No ASCII Box Art):**
   Never author raw ASCII box drawings, faux monospace tables, or wireframe diagrams inside code fences (` ``` `). All visual structures must leverage Obsidian-native markdown primitives:
   - **Tabular Data & Claim Comparison Matrices**: Use standard GitHub-Flavored Markdown (GFM) tables (`| Col 1 | Col 2 |`).
   - **Causal Chains, Timelines, & Command Hierarchies**: Use native `mermaid` diagrams (`flowchart TD`, `flowchart LR`, `sequenceDiagram`).
   - **5W1H Intelligence Anchors & SITREP Cards**: Use native Obsidian Callouts (`> [!NOTE]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!EXAMPLE]`).
   - **Mermaid Clean Label Invariant**: Diagram node labels and edge descriptions must NEVER contain Obsidian wikilinks (`[[...]]`) or unquoted special characters (`:`, `&`, `(`, `)`). Double brackets `[[...]]` define subroutine shapes in Mermaid syntax and cause parse errors and broken SVG rendering in Obsidian. All node labels must be clean plain text wrapped in double quotes (e.g., `NODE["Clean Label Text"]`). Wikilinks belong strictly in markdown prose, tables, and `## Related Primitives`.
8. **Graph-First Indexing & Retrieval via `ki` (Knowledge Index) & Sovereign ArcadeDB Multi-Model Store:**
   The `ki` CLI and ArcadeDB (`arcadedb-news`) provide core AST search, navigation, and hybrid GraphRAG retrieval for `wiki/`.
   - **Vault Root & Directory Context**: The `ki` vault marker (`.ki/vault.yaml`) is located in `wiki/`. When running `ki` from the repository root, always specify `-C wiki`. Paths passed to `ki add` or `ki rm` must be relative to `wiki/` (e.g., `events/2026-10-25 El Fasher Grand Market Shelling.md`, `actors/Rapid Support Forces.md`, `citations/<citation>.md`, `sources/<slug>.md`).
   - **Targeted Discovery & Semantic Search**: Use `ki search`, `ki outline`, and `ki get` for exploratory queries, dialectical investigations (Protocol B), and cross-vault slice retrieval. Standard direct file reading (`view_file`) is permitted during ingestion scoping (`wiki/index.md`, `wiki/glossary.md`) and node refactoring.
   - **Incremental Index Synchronization**: Whenever notes in `wiki/` are created or refactored, synchronize them using `ki add -C wiki "<relative-path>"` (one file per invocation) or `./scripts/sync_vault_graph.sh`.
9. **Dual-Flow Chain of Thought (CoT) Invariant for News & Conflict Intelligence:**
   Knowledge compilation must preserve investigative and causal reasoning across both intra-document section flows (Micro-CoT) and inter-document graph relationships (Macro-CoT).
   - **Event Notes (`wiki/events/`, `type: event`, `subtype: incident | campaign | crisis | diplomatic`)**:
     1. `1. Event Anchor & 5W1H Summary` (`EVENT_ANCHOR`)
     2. `2. Chronological Sequence & Tactical Mechanics ("What & How")` (`CHRONOLOGICAL_MECHANICS`)
     3. `3. Causal Drivers & Strategic Motives ("Why")` (`CAUSAL_MOTIVES`)
     4. `4. Humanitarian, Territorial & Geopolitical Impact` (`IMPACT_ASSESSMENT`)
     5. `5. Competing Narratives, Attribution & Contradictions` (`CONTRADICTION_MATRIX`)
     6. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Actor Notes (`wiki/actors/`, `type: actor`, `subtype: state_force | armed_group | political_body | civil_society | person | media_source`)**:
     1. `1. Identity, Classification & Leadership Anchor` (`ACTOR_ANCHOR`)
     2. `2. Historical Lineage, Factions & Command Structure` (`COMMAND_LINEAGE`)
     3. `3. Strategic Objectives, Ideology & Political Economy ("Why")` (`STRATEGIC_DOCTRINE`)
     4. `4. Operational Capabilities, Alliances & Foreign Backing` (`ALLIANCE_NETWORK`)
     5. `5. Chronological Event Footprint & Accountability Record` (`EVENT_FOOTPRINT`)
     6. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Location Notes (`wiki/locations/`, `type: location`, `subtype: country | state_adm1 | locality_adm2 | city_town | neighborhood_site | idp_camp | infrastructure | border_crossing`)**:
     1. `1. Geopolitical Identity & Strategic Significance` (`LOCATION_ANCHOR`)
     2. `2. Territorial Control History & Armed Presence` (`TERRITORIAL_CONTROL`)
     3. `3. Key Infrastructure, Trade Corridors & Resources` (`INFRASTRUCTURE_LOGISTICS`)
     4. `4. Humanitarian Status, Displacement & Civil Services` (`HUMANITARIAN_STATUS`)
     5. `5. Chronological Log of Major Conflict Events` (`EVENT_LOG`)
     6. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Theme Notes (`wiki/themes/`, `type: theme`, `subtype: war_economy | humanitarian_driver | military_doctrine | political_dynamic | information_warfare`)**:
     1. `1. Core Thesis & Structural Mechanism ("Why")` (`DEFINITIONAL_ANCHOR`)
     2. `2. Historical Roots & Political Economy Anatomy` (`MECHANISTIC_DEEPEN`)
     3. `3. Operational Manifestations Across Frontlines` (`MANIFESTATION_TRAP`)
     4. `4. Humanitarian, Regional & Diplomatic Consequences` (`IMPACT_ASSESSMENT`)
     5. `5. Empirical Debates, Uncertainties & Competing Analyses` (`EMPIRICAL_BOUNDARY`)
     6. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Timeline Notes (`wiki/timelines/`, `type: timeline`, `subtype: monthly_chronicle | campaign_timeline | thematic_timeline | diplomatic_timeline`)**:
     1. `1. Temporal Scope, Theatre Coverage & Strategic Periodization` (`TIMELINE_ANCHOR`)
     2. `2. Chronological Event & Citation Ledger (Bitemporal Sequence)` (`CHRONOLOGICAL_LEDGER`)
     3. `3. Causal Escalation Chains, Turning Points & Tempo Analysis` (`CAUSAL_ESCALATION`)
     4. `4. Cumulative Humanitarian, Territorial & Attribution Telemetry` (`CUMULATIVE_TELEMETRY`)
     5. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Citation Notes (`wiki/citations/`, `type: citation`, `subtype: official_statement | eyewitness_testimony | military_communique | forensic_finding | diplomatic_resolution`)**:
     1. `1. Speaker Provenance, Institutional Role & Context` (`CITATION_ANCHOR`)
     2. `2. Verbatim Bilingual Citation & Forensic Text` (`VERBATIM_EVIDENCE`)
     3. `3. Substantive Claims, Event Grounding & Contradiction Impact` (`FORENSIC_GROUNDING`)
     4. `## Related Primitives` (`SYNTHESIS_CATALOG`)
   - **Macro-CoT Relational Handshakes**:
     - *Causal & Temporal Flow*: `[:CHRONICLES]`, `[:PRECEDES]`, `[:TRIGGERS]`, `[:RETALIATES_FOR]`, `[:PART_OF_CAMPAIGN]`, `[:MOTIVATED_BY]`.
     - *Actor Agency & Participation*: `[:PERPETRATED_BY]`, `[:TARGETED]`, `[:PARTICIPATED_IN]`, `[:COMMANDED_BY]`, `[:ALLIED_WITH]`, `[:SPONSORED_BY]`, `[:DEFECTED_TO]`, `[:AFFILIATED_WITH]`, `[:PUBLISHED_BY]`, `[:STATED]`.
     - *Spatio-Political*: `[:OCCURRED_AT]`, `[:LOCATED_IN]`, `[:CONTROLS_TERRITORY]`, `[:DISPLACES_POPULATION]`.
     - *Provenance, Citation & Contradiction*: `[:EMPIRICALLY_GROUNDS]`, `[:CONTAINS_CITATION]`, `[:TESTIFIES_TO]`, `[:CORROBORATES]`, `[:CONTRADICTS_CLAIM]`, `[:ATTRIBUTES_BLAME_TO]`, `[:DEBUNKS]`.
10. **ArcadeDB Dialect, Documentation & Multi-Model Invariant:**
    When querying, modeling, migrating, benchmarking, or integrating ArcadeDB:
    - **Documentation Grounding**: Strictly adhere to the latest ArcadeDB documentation (`https://docs.arcadedb.com/`) and workspace rules in `.agent/rules/arcadedb.md`.
    - **No ANSI JOIN Invariant**: ArcadeDB SQL does not support ANSI relational `JOIN`. Use graph traversal operators (`out()`, `in()`, `both()`, `expand()`) or OpenCypher `MATCH`.
    - **Native In-Engine Procedures**: Leverage ArcadeDB's native Graph OLAP procedures (`algo.fastrp`, `algo.pagerank`, `algo.betweenness`, `algo.louvain`, `algo.node2vec`) and JVector (`LSM_VECTOR`).
    - **REST & Protocol Routing**: Execute reads via `POST /api/v1/query/{db}` (preferring Cypher), writes via `POST /api/v1/command/{db}`, and bulk streams via `POST /api/v1/batch/{db}`.

---

## 2. Directory Topography

- `raw/`: Immutable multilingual primary evidence repository (READ-ONLY).
  - `raw/articles/`: News articles in Arabic, English, French, German, etc.
  - `raw/social/`: Archived Telegram communiqués, X threads, Facebook posts.
  - `raw/videos/`: Video recordings (`.mp4`, `.mov`) and field footage.
  - `raw/transcripts/`: Full-text bilingual transcripts with timestamped citations.
  - `raw/reports/`: Humanitarian, UN OCHA, IPC, ACLED, and NGO reports (PDF/Markdown).
  - `raw/satellite/`: Remote sensing and geospatial imagery dossiers (e.g., Yale HRL, Sudan Witness).
  - `raw/assets/`: Downloaded images, maps, and geolocation frames.
- `_input/`: Operational workspace for tasks, research dossiers, and user deliverables.
  - `_input/tasks/`: Active user task specifications and query briefs tracked on `_input/projects/infra/infrastructure_board.md`.
  - `_input/tasks/archived/`: Completed and archived task specifications.
  - `_input/drafts/`: Working drafts and deliverables produced from tasks.
  - `_input/research/`: Compiled deep web research dossiers (`web-deep-research`).
  - `_input/projects/`: Project trackers and infrastructure Kanban boards.
- `wiki/`: Agent-compiled Sudan News & OSINT Knowledge Graph (READ-WRITE).
  - `wiki/events/`: Discrete conflict/news incidents, military campaigns, diplomatic talks, and crises.
  - `wiki/actors/`: Acting entities (State Forces, Armed Groups, Political Bodies, Civil Society/ERRs, Quoted Persons with institutional roles, and Media Source Outlets).
  - `wiki/locations/`: Geopolitical nodes anchored to UN OCHA Sudan P-Codes (`ADM1` States, `ADM2` Localities, Cities, IDP Camps, Infrastructure, Border Crossings).
  - `wiki/themes/`: Enduring structural conflict drivers, war economy mechanics, and doctrines ("Why?").
  - `wiki/timelines/`: Monthly chronicles (`YYYY-MM Sudan Conflict Chronicle`), campaign timelines, thematic timelines, and diplomatic timelines tracking Bitemporal sequences ($t_{\text{valid}}$ vs. $t_{\text{reported}}$).
  - `wiki/citations/`: Standalone verbatim citations, official statements, military communiqués, and eyewitness testimonies linked to their speaker (`Actor: person`) and originating `Source`.
  - `wiki/sources/`: Per-artifact provenance distillations with NATO Admiralty ratings (`A1`–`F6`).
  - `wiki/syntheses/`: Archived analytical outputs from complex `/query` investigations.
  - `wiki/ingestions/`: Chronological ingestion audit dossiers (`wiki/ingestions/YYYY-MM-DD/<source-slug>.md`).
  - `wiki/index.md`: Master catalog mapping every compiled node to a 1-line summary.
  - `wiki/overview.md`: Living Situation Report (SITREP) synthesizing active frontlines, humanitarian telemetry, and major narrative disputes.
  - `wiki/glossary.md`: Cross-lingual entity, kunya, acronym, and UN OCHA P-Code disambiguation registry.
  - `wiki/log.md`: Chronological, append-only operational audit log.

---

## 3. Mandatory Frontmatter Schemas

Every note generated or refactored within `wiki/` must start with valid YAML frontmatter:

### 3.1. Event Note (`wiki/events/`)
```yaml
---
title: "YYYY-MM-DD Canonical Event Title"
type: "event"
subtype: "incident" # Options: incident | campaign | crisis | diplomatic
event_category: "Explosions/Remote violence" # ACLED Category: Battles | Explosions/Remote violence | Violence against civilians | Protests | Riots | Strategic developments
event_sub_type: "Shelling/artillery/missile attack"
event_start_date: YYYY-MM-DDTHH:MM:SSZ # Valid Time (t_valid start)
event_end_date: YYYY-MM-DDTHH:MM:SSZ   # Valid Time (t_valid end)
time_precision: "day" # Options: exact_time | day | week | month
reported_date: YYYY-MM-DD # Report Time (t_reported)
last_updated: YYYY-MM-DD  # Compilation Time (t_compiled)
locations: ["[[Location Name]]"]
pcode: "SD02001"
geo_precision: "city_town" # Options: exact_coords | neighborhood_site | city_town | locality_adm2 | state_adm1
actors_involved:
  - actor: "[[Actor Name]]"
    role: "belligerent" # Options: perpetrator | alleged_perpetrator | target | belligerent | mediator | responder
parent_campaign: "[[Campaign Title]]"
fatalities_low: 0
fatalities_best: 0
fatalities_high: 0
verification_status: "corroborated_with_contradictions" # Options: confirmed | corroborated_with_contradictions | single_source | disputed | debunked
admiralty_rating: "B2" # A-F Source Reliability + 1-6 Info Credibility
reliability_score: 0.85
contradiction_flags: [] # Options: ATTRIBUTION_CONFLICT | MAGNITUDE_DISCREPANCY | TARGET_FRAMING_CONFLICT | TEMPORAL_CAUSAL_INVERSION | CONTROL_DISPUTE | MEDIA_FABRICATION_DEBUNK
tags: [theatre-tag, event-type-tag]
sources: ["[[sources/source-slug]]"]
aliases: ["Alternative Name", "Arabic Title"]
---
```

### 3.2. Actor, Location, Theme, Timeline, Citation & Source Notes
All other `wiki/` notes require:
```yaml
---
title: "Canonical Title"
type: "actor" # Options: actor | location | theme | timeline | citation | source | synthesis | ingestion
subtype: "armed_group" # Mandatory for actor, location, theme, timeline, citation, source
tags: [domain-tag, status-tag]
last_updated: YYYY-MM-DD
sources: ["[[sources/source-slug]]"]
aliases: ["Alternative Name", "Arabic Script", "Acronym"]
admiralty_rating: "B2" # Mandatory for source, citation, timeline, and event notes
reliability_score: 0.85 # 0.0 to 1.0 derived from Admiralty rating / verification strength
---
```
- **Additional `location` fields**: `adm_level` (`0`–`4`), `parent_location`, `pcode` (UN OCHA P-Code), `coordinates` (`[lat, lon]`), `current_control`, `humanitarian_ipc_phase` (`1`–`5`).
- **Additional `actor` fields**: `acled_actor_type`, `leader`, `allies`, `opponents`, `areas_of_operation`.
  - **For `actor` (`subtype: "person"`)**: `role_title` (e.g., `"UN High Commissioner for Human Rights"`), `affiliated_organization` (e.g., `"[[OHCHR]]"`).
  - **For `actor` (`subtype: "media_source"`)**: `parent_organization`, `editorial_alignment`, `baseline_admiralty_reliability` (`A`–`F`), `url`.
- **Additional `timeline` fields**: `subtype` (`monthly_chronicle | campaign_timeline | thematic_timeline | diplomatic_timeline`), `start_date` (`YYYY-MM-DD`), `end_date` (`YYYY-MM-DD`), `time_horizon` (`week | month | quarter | year | multi_year`), `theatres_covered`, `events_chronicled`, `citations_chronicled`, `actors_involved`, `themes_linked`, `cumulative_fatalities_low`, `cumulative_fatalities_best`, `cumulative_fatalities_high`, `admiralty_rating`.
- **Additional `citation` fields**: `speaker` (`"[[Person Name]]"`), `speaker_role`, `affiliated_organization` (`"[[Organization]]"`), `source_note` (`"[[sources/source-slug]]"`), `source_outlet` (`"[[Outlet Name]]"`), `citation_date` (`YYYY-MM-DD`), `original_language` (`ar | en | fr | de`), `speech_act` (`condemnation | attribution_claim | denial | eyewitness_account | casualty_report | ceasefire_call | war_crimes_warning`), `events_referenced`, `actors_referenced`, `locations_referenced`, `themes_referenced`.
- **Additional `source` fields**: `status` (`"draft" | "approved"`), `compiled` (`false | true`), `compiled_at`, `source_outlet` (`"[[Outlet Name]]"` — must correspond to a `subtype: media_source` actor in `wiki/actors/`), `raw_file`, `language` (`ar | en | fr | de`), `published_date`, `alignment` (`independent | pro_saf | pro_rsf | state_media | civil_society_err | international_org | osint_verified`), `events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `timelines_to_create`, `citations_to_create`, `nodes_to_refactor`.

---

## 4. Operational Protocols

### Protocol A: Two-Phase Ingestion (`/ingest <path>`)

Ingestion is split into two explicit phases separated by a human-in-the-loop review gate on `wiki/sources/<source-slug>.md` (`status: "draft" | "approved"`):

#### Phase 1: Source Distillation & Scoping (`/ingest <raw-file-path>`)
When directed to ingest a primary evidence document from `raw/` (or `_input/research/`):
1. **Verification:** Verify that the file exists and treat it as strictly immutable.
2. **Context Retrieval, Deduplication & Scoping (`wiki-scope`):**
   - Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
   - **48-Hour Spatio-Temporal Event Deduplication Check**: For every candidate event in the source, check whether an existing note in `wiki/events/` occurred within $\lvert \Delta t_{\text{valid}} \rvert \le 48\text{ hours}$ at the same location (`wiki/locations/`) involving overlapping actors. If a match exists, classify the event under **Nodes to Refactor** rather than creating a duplicate event note.
   - **Mandatory Source Outlet, Quoted Person/Citation & Monthly/Thematic Timeline Extraction**:
     - Always scope the `source_outlet` as an `Actor` (`subtype: "media_source"`).
     - Extract every named speaker/eyewitness in Section 3 (`## 3. Bilingual Direct Citations & Forensic Evidence`) as an `Actor` (`subtype: "person"`) with `role_title` and `affiliated_organization`.
     - Extract every key direct statement/testimony in Section 3 into `citations_to_create` (`wiki/citations/`, `type: "citation"`).
     - **Mandatory Monthly Chronicle & Campaign/Thematic Timeline Rule**: For every calendar month `YYYY-MM` covered by candidate events in the source, check whether `[[YYYY-MM Sudan Conflict Chronicle]]` exists in `wiki/timelines/`. If it does not exist, add `[[YYYY-MM Sudan Conflict Chronicle]]` (`subtype: "monthly_chronicle"`) to `timelines_to_create`. If it already exists, add `[[YYYY-MM Sudan Conflict Chronicle]]` to `nodes_to_refactor` so the newly ingested events and citations are appended to its Bitemporal Ledger. Additionally, scope a `campaign_timeline` or `thematic_timeline` whenever the source documents a multi-incident campaign or doctrinal escalation sequence.
   - Separate candidate primitives into **New Events (`$E$`)**, **New Actors (`$A$`, including armed/political entities, quoted `person` actors, and the `media_source` outlet)**, **New Locations (`$L$`)**, **New Themes (`$T$`)**, **New Timelines (`$TL$`)**, **New Citations (`$C$`)**, and **Nodes to Refactor (`$K$`)**, applying the **News & OSINT Significance Filter** ($\ge 0.70$ composite score).
3. **Draft Source Creation (`wiki/sources/<source-slug>.md`):**
   - Create `wiki/sources/<source-slug>.md` with `status: "draft"` and `compiled: false` in YAML frontmatter, alongside the **NATO Admiralty Rating (`A1`–`F6`)**, `alignment`, `language`, `reliability_score`, and the planned target arrays (`events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `timelines_to_create`, `citations_to_create`, `nodes_to_refactor`).
   - Author the 5-section source body: `## 1. 5W1H Source Intelligence Summary & Provenance`, `## 2. Atomic Extracted Claims Table`, `## 3. Bilingual Direct Citations & Forensic Evidence` (linking each blockquote to its `[[Speaker]]`, `[[Organization]]`, and `[[Citation Entity]]`), `## 4. Scoped Ingestion Plan (Pending Approval)`, and `## 5. Related Primitives`.
4. **Log & Halt for Review:**
   - Append to `wiki/log.md`:
     `## [YYYY-MM-DD] ingest-draft | <source-slug> | Created draft source note in wiki/sources/<source-slug>.md (status: draft) with scoped manifest (E events, A actors, L locations, T themes, TL timelines, C citations, K refactors); awaiting approval.`
   - **HALT** before creating or modifying any notes in `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/citations/`, or `wiki/ingestions/`, and before indexing into ArcadeDB (`news`) or `ki`. Prompt the user to review `wiki/sources/<source-slug>.md` and change `status: "draft"` to `status: "approved"`.

#### Phase 2: Approved Entity Compilation & Database Sync (`/ingest wiki/sources/<source-slug>.md` or `/ingest --approved`)
When directed to continue ingestion on an approved source note (or all source notes where `status: "approved"` and `compiled: false`):
1. **Approval Verification:** Read `wiki/sources/<source-slug>.md` and verify `status: "approved"` and `compiled: false`. (If `status: "draft"`, halt and remind the user to set `status: "approved"` first).
2. **Workload-Optimized Multi-Node Compilation:**
   - Read the approved target node lists (`events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `timelines_to_create`, `citations_to_create`, `nodes_to_refactor`) and Atomic Extracted Claims Table from `wiki/sources/<source-slug>.md`.
   - Strictly enforce **Axiom 4 (Clean Wikilinks & Escaped Table Pipes)**, **Axiom 7 (Zero ASCII Box Art)**, and **Axiom 9 (Dual-Flow CoT Section Arcs for `events`, `actors`, `locations`, `themes`, `timelines`, `citations`)**.
   - Cross-reference `wiki/glossary.md` for every actor and location to prevent transliteration splitting (e.g., *Hemedti* $\to$ `[[Mohamed Hamdan Dagalo]]`, *Gezira* $\to$ `[[Al Jazirah]]`).
   - When refactoring an existing Event note with conflicting source claims, update `## 5. Competing Narratives, Attribution & Contradictions` and `contradiction_flags`.
3. **Ingestion Dossier & Source Finalization:**
   - Author the audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` (`type: ingestion`) recording Provenance, Scoped Ingestion Manifest, Compiled Nodes Table, Refactored Nodes & Contradictions Tracked, and Verification Telemetry.
   - Update `wiki/sources/<source-slug>.md` frontmatter to `compiled: true` and `compiled_at: YYYY-MM-DD`.
4. **Batch Catalog, Ledger, and Graph Database Synchronization:**
   - Update `wiki/index.md` (including the newly approved source note and all compiled domain, timeline, and citation nodes), `wiki/glossary.md`, and `wiki/overview.md` (if frontline control, humanitarian metrics, or strategic debates shifted).
   - Synchronize the `ki` index and ArcadeDB (`news`) database via `./scripts/sync_vault_graph.sh` and `python3 scripts/ingest_to_arcadedb.py`, and verify `ki status -v -C wiki` reports `✓ READY`.
   - Append to `wiki/log.md`:
     `## [YYYY-MM-DD] ingest-compile | <source-slug> | Compiled approved source into N notes (E events, A actors, L locations, T themes, TL timelines, C citations, K refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index, SITREP & glossary; synced ki & ArcadeDB.`

### Protocol B: Dialectical Intelligence Query (`/query <prompt>`)

When answering complex research or intelligence queries:
1. **Targeted Discovery (`ki search` & `ki outline`):** Discover candidate events, actors, locations, and themes across `wiki/`.
2. **Slice Retrieval (`ki get` & Graph Traversal):** Retrieve targeted slices via `ki get --type full "<uri>"` and execute Cypher queries against ArcadeDB for causal chains (`[:TRIGGERS]`, `[:RETALIATES_FOR]`), territorial control (`[:CONTROLS_TERRITORY]`), or contradiction audits (`[:CONTRADICTS_CLAIM]`).
3. **Synthesis & Causal/Timeline Scaffolding:** Synthesize an answer grounded in explicit `[[wikilink]]` citations, Admiralty ratings, and Mermaid causal timelines (`flowchart TD` / `flowchart LR`).
4. Prompt the user: *"Would you like this response archived into `wiki/syntheses/`?"* and, if affirmed, save to `wiki/syntheses/<query-slug>.md`, update `wiki/index.md`, sync via `ki add`, and log in `wiki/log.md`.

### Protocol C: Graph Linting (`/lint`)

Perform an automated audit of the vault:
1. **Index Parity Audit:** Run `ki status -v -C wiki` to detect drifted, unindexed, or deleted notes.
2. **Vault Syntax, Link & Schema Audit:** Run `python3 scripts/lint_vault.py` to detect orphan notes, dead links, backticked wikilinks (`` `[[...]]` ``), unescaped table pipes, Mermaid label errors, and missing mandatory frontmatter fields (`admiralty_rating`, `pcode`, `event_start_date`, etc.).
3. **Output:** Render a diagnostic Markdown table with recommended remediation actions.

### Protocol D: Task-Driven Querying & Drafting (`/task <file-path>`)

When directed to execute a task specification from `_input/tasks/`:
1. **Task Ingestion & Verification:** Confirm the task exists in `_input/tasks/`, read directives, and move its card on `_input/projects/infra/infrastructure_board.md` to `## ⚡ In Progress`.
2. **Context Resolution & Deliverable Production:** Ground analysis in `wiki/` and author the deliverable in `_input/drafts/<deliverable-title>.md` (or `_input/research/` for deep research tasks).
3. **Task Archival & Kanban Synchronization:** Update task frontmatter to `status: "done"`, move the task file to `_input/tasks/archived/<task-file>.md`, update its card on `_input/projects/infra/infrastructure_board.md` to `## ✅ Done`, and log the execution in `wiki/log.md`.
