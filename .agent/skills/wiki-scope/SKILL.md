---
name: wiki-scope
description: Scans a news or OSINT source document before ingestion, performs 48-hour spatio-temporal event deduplication against existing vault catalogs, extracts the source_outlet, quoted person actors, and standalone citations, filters by intelligence significance, and generates a Scoped Ingestion Manifest persisted into the draft source note.
---

# Wiki Scope Skill (`wiki-scope`)

## Objective
Act as the mandatory epistemic reconnaissance, deduplication, and planning phase prior to compiling any primary news article, social media post, video transcript, or OSINT report from `raw/` into the `wiki/` knowledge graph.

Instead of imposing static extraction limits or creating duplicate event nodes across multiple media reports, `wiki-scope` cross-references the incoming source against `wiki/index.md` and `wiki/glossary.md`, executes **48-Hour Spatio-Temporal Event Deduplication**, separates candidate primitives into **Events**, **Actors** (including acting forces, quoted **Person Actors** with institutional roles, and the publishing **Source Outlet**), **Locations**, **Themes/Timelines**, **Standalone Citations (`wiki/citations/`)**, and **Nodes to Refactor**, and persists the **Scoped Ingestion Manifest** directly into the Phase 1 draft source note (`wiki/sources/<source-slug>.md`).

---

## Execution Sequence

### 1. Document & Vault Cross-Referencing
1. Read the target document in `raw/` (or `_input/research/`) using `view_file`.
2. Read `wiki/index.md` and `wiki/glossary.md` to map existing vault topography, Arabic/English aliases, kunyas, and UN OCHA P-Codes (`SD01`–`SD18`).
3. Extract candidate primitives into six distinct pools:
   - **Candidate Events (`wiki/events/`)**: Discrete conflict incidents (`incident`), multi-day military operations (`campaign`), diplomatic talks/agreements (`diplomatic`), or humanitarian emergencies (`crisis`).
   - **Candidate Actors (`wiki/actors/`)**:
     - *Armed, State, Political & Civil Society Entities*: State forces (`state_force`), paramilitaries/rebel groups/militias (`armed_group`), political coalitions/international bodies (`political_body`), and civil society/ERRs/NGOs (`civil_society`).
     - *Source Outlet (`subtype: "media_source"`)*: The originating media outlet or news agency (`source_outlet`, e.g., `[[UN News]]`, `[[Radio Dabanga]]`, `[[Sudan Tribune]]`) MUST always be scoped as an `Actor` (`subtype: "media_source"`). If it does not exist in `wiki/actors/`, add it to `actors_to_create`; if it already exists, add it to `nodes_to_refactor`.
     - *Quoted Persons (`subtype: "person"`)*: Every named official, military commander, spokesperson, or key eyewitness delivering a direct citation or testimony in Section 3 (`## 3. Bilingual Direct Citations & Forensic Evidence`) MUST be scoped as an `Actor` (`subtype: "person"`) with `role_title` (e.g., `"UN High Commissioner for Human Rights"`, `"Commander, UNISFA Pakistani Battalion"`) and `affiliated_organization` (e.g., `"[[OHCHR]]"`, `"[[UNISFA]]"`).
   - **Candidate Locations (`wiki/locations/`)**: Sudan States (`state_adm1`), Localities (`locality_adm2`), Cities/Towns (`city_town`), Neighborhoods/Sites (`neighborhood_site`), IDP Camps (`idp_camp`), Infrastructure (`infrastructure`), and Border Crossings (`border_crossing`).
   - **Candidate Themes (`wiki/themes/`)**: Enduring structural drivers ("Why?"), war economy supply chains, or military doctrines.
   - **Candidate Timelines (`wiki/timelines/`, `type: "timeline"`)**:
     - *Mandatory Monthly Chronicle (`subtype: "monthly_chronicle"`)*: For every calendar month `YYYY-MM` covered by candidate events in the source, check whether `[[YYYY-MM Sudan Conflict Chronicle]]` exists in `wiki/timelines/`. If it does not exist, add `[[YYYY-MM Sudan Conflict Chronicle]]` to `timelines_to_create`. If it already exists, add `[[YYYY-MM Sudan Conflict Chronicle]]` to `nodes_to_refactor` so the newly extracted events, dated sub-incidents, and citations are appended to its Bitemporal Ledger.
     - *Campaign, Thematic & Diplomatic Timelines (`subtype: campaign_timeline | thematic_timeline | diplomatic_timeline`)*: Scope a dedicated longitudinal timeline whenever the source documents a multi-incident campaign corridor, a dated doctrinal escalation sequence (e.g., `[[Sudan Drone Warfare and Double-Tap Strike Timeline]]`), or a multi-step diplomatic/accountability track.
   - **Candidate Standalone Citations (`wiki/citations/`, `type: "citation"`)**: Every key direct statement, official condemnation, military communiqué, or eyewitness testimony extracted in Section 3 (`## 3. Bilingual Direct Citations & Forensic Evidence`) is scoped into `citations_to_create` as a standalone note `[[YYYY-MM-DD <Speaker Name> <Concise Statement Topic>]]` (`subtype: official_statement | eyewitness_testimony | military_communique | forensic_finding | diplomatic_resolution`), linking the speaker (`Actor: person`), their `affiliated_organization`, the `source_note`, the `source_outlet`, and the referenced events/locations/themes.
   - **Existing Nodes to Refactor**: Notes already present in `wiki/` where the new source introduces corroborating evidence, updated casualty/displacement counts, shifts in territorial control, new entries for an existing `[[YYYY-MM Sudan Conflict Chronicle]]`, or **competing/contradictory narratives**.

### 2. 48-Hour Spatio-Temporal Event Deduplication Rule
Before proposing any **New Event**, verify whether an existing Event note in `wiki/events/` covers the same real-world incident:
$$\lvert t_{\text{valid}}(\text{candidate}) - t_{\text{valid}}(\text{existing}) \rvert \le 48\text{ hours} \quad \land \quad \text{Location}(\text{candidate}) \cap \text{Location}(\text{existing}) \neq \emptyset$$
- **If a match exists**: Do **NOT** create a new Event note. Classify the existing Event note under **Nodes to Refactor** (to append the new source, update casualty ranges, or record competing claims in `## 5. Competing Narratives, Attribution & Contradictions`).
- **If no match exists**: Propose a new canonical Event note named `YYYY-MM-DD <Canonical Event Title>.md` (for discrete incidents) or `<Campaign Title>.md` (for campaigns).

### 3. News & OSINT Significance Filtering
Filter candidate nodes using three qualitative criteria (must score $\ge 0.70$ on composite significance):
- **5W1H Evidentiary Specificity**: Does the candidate event, actor, location, timeline, or citation possess concrete spatio-temporal anchoring, identifiable actors/speakers, or verifiable impact?
- **Network & Causal Interconnectivity**: Can this node connect to $\ge 2$ existing or planned nodes (e.g., linking a `Timeline` via `[:CHRONICLES]` to its ordered `Event` and `Citation` nodes)?
- **Sudan Domain Relevance**: Does the item directly advance intelligence tracking across kinetic frontlines, humanitarian crisis indicators, political economy, or OSINT verification?

### 4. Generate & Persist the Scoped Ingestion Manifest
Persist the candidate node lists in two places inside the Phase 1 draft source note (`wiki/sources/<source-slug>.md`):
1. **YAML Frontmatter Arrays**: `events_to_create`, `actors_to_create`, `locations_to_create`, `themes_to_create`, `timelines_to_create`, `citations_to_create`, `nodes_to_refactor`.
2. **Markdown Body (`## 4. Scoped Ingestion Plan (Pending Approval)`)**:

```markdown
## 4. Scoped Ingestion Plan (Pending Approval)

> [!WARNING] Phase 1 Review Gate (`status: "draft"`)
> Review the extracted claims, NATO Admiralty rating, and planned node operations below. When ready to compile these entities into `wiki/` and update the ArcadeDB (`news`) & `ki` indexes, change `status: "draft"` to `status: "approved"` in the frontmatter and run `/ingest wiki/sources/<source-slug>.md` (or `/ingest --approved`).

### 4.1. Candidate New Events (E)
- [[YYYY-MM-DD Event Title]] (`subtype: incident | campaign | crisis | diplomatic`): 1-line 5W1H summary & ACLED category.

### 4.2. Candidate New Actors — Forces, Organizations, Source Outlet & Quoted Persons (A)
- [[Outlet Name]] (`subtype: media_source`, `alignment: ...`): Originating `source_outlet`.
- [[Organization or Force Name]] (`subtype: state_force | armed_group | political_body | civil_society`): Role and ACLED actor type.
- [[Person Name]] (`subtype: person`, `role_title: "..."`, `affiliated_organization: "[[Organization]]"`): Quoted official, commander, spokesperson, or eyewitness.

### 4.3. Candidate New Locations (L)
- [[Location Name]] (`pcode: SD...`, `subtype: city_town | ...`): Admin hierarchy and current control status.

### 4.4. Candidate New Themes (T)
- [[Theme Title]] (`subtype: military_doctrine | war_economy | ...`): Structural driver ("Why?").

### 4.5. Candidate New Timelines (TL)
- [[YYYY-MM Sudan Conflict Chronicle]] (`subtype: monthly_chronicle`): Bitemporal monthly ledger of all dated incidents and citations.
- [[Campaign or Thematic Timeline Title]] (`subtype: campaign_timeline | thematic_timeline | diplomatic_timeline`): Longitudinal escalation sequence.

### 4.6. Candidate New Citations (C)
- [[YYYY-MM-DD Speaker Name Statement Topic]] (`subtype: official_statement | eyewitness_testimony | ...`, `speaker: "[[Person Name]]"`): Direct verbatim statement or forensic testimony from Section 3.

### 4.7. Existing Nodes to Refactor (K)
- [[Existing Note]]: Specific update (e.g., merge corroborating source, append new dated rows to an existing `[[YYYY-MM Sudan Conflict Chronicle]]`, update casualty range, or add `ATTRIBUTION_CONFLICT` to Section 5 Contradiction Matrix).
```

### 5. Hand-off to Phase 1 Source Distillation
- Hand the Scoped Ingestion Manifest directly to `wiki-ingest` (Phase 1) so `wiki/sources/<source-slug>.md` is authored with `status: "draft"` and `compiled: false` and halted for user review.
