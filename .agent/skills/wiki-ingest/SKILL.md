---
name: wiki-ingest
description: Compiles multilingual news articles, social media posts, transcripts, PDFs, satellite reports, and videos from raw/ into atomic Obsidian wiki notes (events, actors, locations, themes, timelines, sources) using dynamic pre-scoping, NATO Admiralty scoring, and GRaSP contradiction tracking.
---

# Wiki Ingest Skill (`wiki-ingest`)

## Objective
Ingest uncompiled primary evidence from `raw/` (`raw/articles/`, `raw/social/`, `raw/videos/`, `raw/transcripts/`, `raw/reports/`, `raw/satellite/`), dynamically scope and deduplicate primitives via `wiki-scope`, compile atomic notes across `wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, and `wiki/timelines/`, refactor existing knowledge with explicit contradiction tracking, and synchronize the unified graph index.

---

## Supported Source Types & Parsing Procedures

### 1. News Articles & Social Media Artefacts (`raw/articles/`, `raw/social/`, `_input/research/`)
- Read directly via `view_file`. Preserve original publication timestamps, author/channel handles, and URLs.

### 2. PDF Reports & Satellite Dossiers (`raw/reports/`, `raw/satellite/`)
- View directly via `view_file` (or extract text via `pypdf` for large multi-page documents). Record imagery acquisition dates, coordinates, and thermal/crater findings.

### 3. Spoken Transcripts (`raw/transcripts/`)
- Read full transcript directly and preserve temporal timestamps (e.g., `[04:15]`) in citations.

### 4. Direct Multimodal Video Files (`raw/videos/`)
- **File size < 100 MB**: Ingest directly using `view_file`. Analyze spoken audio (including Arabic speech/chants), uniform insignias, vehicle markings, weapon systems, and visible landmarks for geolocation/chronolocation.
- **File size ≥ 100 MB**: Advise the user to provide or extract the transcript in `raw/transcripts/<slug>.md`.

---

## Execution Sequence

### 1. Path & Immutability Verification
- Confirm the target file exists in `raw/` (or `_input/research/`).
- Never modify, rename, or delete any primary evidence file in `raw/`.

### 2. Pre-Ingestion Scoping & Event Deduplication (`wiki-scope`)
- Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
- Run the `wiki-scope` protocol (including the **48-Hour Spatio-Temporal Event Deduplication Check** and **$\ge 0.70$ News & OSINT Significance Filter**).
- Output the **Scoped Ingestion Manifest** setting dynamic quotas: **$E$ New Events**, **$A$ New Actors**, **$L$ New Locations**, **$T$ New Themes/Timelines**, and **$K$ Nodes to Refactor**.
- **Gating**: If $E + A + L + T \le 6$, proceed automatically. If $> 6$, present the manifest to the user before generating notes.

### 3. Cross-Lingual Normalization & Bilingual Quote Preservation (Axiom 6)
- Translate and compile all narrative prose, event titles, and analysis in `wiki/` exclusively in **English**.
- Cross-reference `wiki/glossary.md` to map Arabic script, Sudanese kunyas (e.g., *Hemedti / حميدتي* $\to$ `[[Mohamed Hamdan Dagalo]]`, *Al-Burhan / البرهان* $\to$ `[[Abdel Fattah al-Burhan]]`), acronyms, and transliteration variants (*Gezira* $\to$ `[[Al Jazirah]]`, *Al-Fashir* $\to$ `[[El Fasher]]`) to canonical node titles.
- In `wiki/sources/<source-slug>.md`, preserve key eyewitness or official quotes in **both English translation and original Arabic/foreign script** inside blockquotes for forensic traceability.

### 4. Source Distillation (`wiki/sources/<source-slug>.md`)
- Author `wiki/sources/<source-slug>.md` with mandatory YAML frontmatter:
  - `title`, `type: "source"`, `subtype` (`news_article | social_post | video_osint | satellite_report | official_communique | ngo_report | eyewitness`), `source_outlet`, `raw_file`, `language`, `published_date`, `ingested_date`, `alignment` (`independent | pro_saf | pro_rsf | state_media | civil_society_err | international_org | osint_verified`), `admiralty_source_reliability` (`A`–`F`), `admiralty_info_credibility` (`1`–`6`), `admiralty_rating` (e.g., `"B2"`), `reliability_score` (`0.0`–`1.0`), `events_covered`, `actors_mentioned`, `locations_mentioned`, `tags`.
- Record:
  1. **5W1H Source Intelligence Summary & Provenance**
  2. **Atomic Extracted Claims Table** (Claim, 5W1H Tuple, Modality [`confirmed | probable | alleged | denied | debunked`], Target Wiki Node)
  3. **Bilingual Direct Citations & Forensic Evidence**
  4. **Related Primitives**

### 5. Multi-Node Compilation & Dual-Flow CoT Enforcement

#### Universal Formatting & Link Invariants (Axioms 4 & 7)
- **Zero ASCII Box Art**: Use GFM tables, Mermaid diagrams, and Obsidian callouts (`> [!NOTE]`). Never use raw ASCII box-drawing characters (`┌`, `└`, `+---+`).
- **Clean Wikilink Invariant**: Never wrap wikilinks in inline code backticks (`` `[[...]]` ``).
- **Table Pipe Invariant**: Escape any internal pipe inside a wikilink in a GFM table as `\|` (e.g., `| [[Target\|Alias]] |`) or use unaliased `[[Target]]`.
- **Shortest Canonical Wikilink Invariant**: Link to events, actors, locations, themes, and timelines using direct titles (`[[El Fasher]]`, `[[Rapid Support Forces]]`), NEVER `[[wiki/locations/El Fasher]]`. Link to sources as `[[sources/<source-slug>]]`.
- **Mermaid Clean Label Invariant**: Never place `[[...]]` or unquoted special characters (`:&()`) inside Mermaid node labels.

#### Ingest-Time Dual-Flow CoT Section Arcs (Axiom 9)
Structure every newly created or refactored note according to its canonical 6-stage epistemic arc:

1. **Event Notes (`wiki/events/`, `type: event`, `subtype: incident | campaign | crisis | diplomatic`)**:
   - Lead Callout: `> [!NOTE] 5W1H Event Intelligence Anchor` (What, When [$t_{\text{valid}}$ vs. $t_{\text{reported}}$], Where [`pcode`], Who, Impact, Admiralty Verification).
   - `## 1. Event Anchor & 5W1H Summary` (`EVENT_ANCHOR`) $\to$ links establish `[:OCCURRED_AT]`, `[:PART_OF_CAMPAIGN]`, `[:INVOLVES_ACTOR]`.
   - `## 2. Chronological Sequence & Tactical Mechanics ("What & How")` (`CHRONOLOGICAL_MECHANICS`) $\to$ links establish `[:PRECEDES]`, `[:PERPETRATED_BY]`, `[:TARGETED]`.
   - `## 3. Causal Drivers & Strategic Motives ("Why")` (`CAUSAL_MOTIVES`) $\to$ links establish `[:TRIGGERED_BY]`, `[:RETALIATES_FOR]`, `[:MOTIVATED_BY]`.
   - `## 4. Humanitarian, Territorial & Geopolitical Impact` (`IMPACT_ASSESSMENT`) $\to$ links establish `[:SHIFTS_CONTROL_TO]`, `[:DISPLACES_POPULATION]`.
   - `## 5. Competing Narratives, Attribution & Contradictions` (`CONTRADICTION_MATRIX`) $\to$ GFM Claim Comparison Matrix contrasting belligerent, local monitor, and OSINT accounts; links establish `[:CORROBORATES]`, `[:CONTRADICTS_CLAIM]`, `[:ATTRIBUTES_BLAME_TO]`, `[:DEBUNKS]`.
   - `## Related Primitives` (`SYNTHESIS_CATALOG`).

2. **Actor Notes (`wiki/actors/`, `type: actor`, `subtype: state_force | armed_group | political_body | civil_society | person | media_source`)**:
   - `## 1. Identity, Classification & Leadership Anchor` (`ACTOR_ANCHOR`)
   - `## 2. Historical Lineage, Factions & Command Structure` (`COMMAND_LINEAGE`) $\to$ `[:COMMANDED_BY]`, `[:SPLINTERED_FROM]`
   - `## 3. Strategic Objectives, Ideology & Political Economy ("Why")` (`STRATEGIC_DOCTRINE`) $\to$ `[:MOTIVATED_BY]`
   - `## 4. Operational Capabilities, Alliances & Foreign Backing` (`ALLIANCE_NETWORK`) $\to$ `[:ALLIED_WITH]`, `[:SPONSORED_BY]`
   - `## 5. Chronological Event Footprint & Accountability Record` (`EVENT_FOOTPRINT`) $\to$ `[:PARTICIPATED_IN]`, `[:CONTROLS_TERRITORY]`
   - `## Related Primitives` (`SYNTHESIS_CATALOG`).

3. **Location Notes (`wiki/locations/`, `type: location`, `subtype: country | state_adm1 | locality_adm2 | city_town | neighborhood_site | idp_camp | infrastructure | border_crossing`)**:
   - `## 1. Geopolitical Identity & Strategic Significance` (`LOCATION_ANCHOR`) $\to$ `[:LOCATED_IN]`
   - `## 2. Territorial Control History & Armed Presence` (`TERRITORIAL_CONTROL`)
   - `## 3. Key Infrastructure, Trade Corridors & Resources` (`INFRASTRUCTURE_LOGISTICS`)
   - `## 4. Humanitarian Status, Displacement & Civil Services` (`HUMANITARIAN_STATUS`)
   - `## 5. Chronological Log of Major Conflict Events` (`EVENT_LOG`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`).

4. **Theme Notes (`wiki/themes/`, `type: theme`, `subtype: war_economy | humanitarian_driver | military_doctrine | political_dynamic | information_warfare`)**:
   - `## 1. Core Thesis & Structural Mechanism ("Why")` (`DEFINITIONAL_ANCHOR`)
   - `## 2. Historical Roots & Political Economy Anatomy` (`MECHANISTIC_DEEPEN`)
   - `## 3. Operational Manifestations Across Frontlines` (`MANIFESTATION_TRAP`)
   - `## 4. Humanitarian, Regional & Diplomatic Consequences` (`IMPACT_ASSESSMENT`)
   - `## 5. Empirical Debates, Uncertainties & Competing Analyses` (`EMPIRICAL_BOUNDARY`)
   - `## Related Primitives` (`SYNTHESIS_CATALOG`).

### 6. Ingestion Dossier Generation (`wiki/ingestions/YYYY-MM-DD/<source-slug>.md`)
- Author a standalone audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` (`type: "ingestion"`), listing `events_created`, `actors_created`, `locations_created`, `themes_created`, `nodes_refactored`, and `contradictions_logged`.

### 7. Batch Catalog, Ledger & Graph Synchronization
- Register new actors, locations (with P-Codes), and Arabic/English aliases in `wiki/glossary.md`.
- Add all newly created notes with 1-line summaries to `wiki/index.md`.
- Update `wiki/overview.md` (Living SITREP) if territorial control, humanitarian indicators, or major narrative contradictions shifted.
- Synchronize the graph via `ki add -C wiki "<relative-path>"` (for $\le 3$ files) or `./scripts/sync_vault_graph.sh` (for $> 3$ files) and verify `ki status -v -C wiki` reports `✓ READY`.
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest | <source-slug> | Compiled into N notes (E events, A actors, L locations, T themes, K refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index, SITREP & glossary; synced graph.`
