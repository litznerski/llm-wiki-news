---
name: wiki-scope
description: Scans a news or OSINT source document before ingestion, performs 48-hour spatio-temporal event deduplication against existing vault catalogs, filters by intelligence significance, and generates a Scoped Ingestion Manifest with dynamic Event, Actor, Location, and Theme quotas.
---

# Wiki Scope Skill (`wiki-scope`)

## Objective
Act as the mandatory epistemic reconnaissance, deduplication, and planning phase prior to compiling any primary news article, social media post, video transcript, or OSINT report from `raw/` into the `wiki/` knowledge graph.

Instead of imposing static extraction limits or creating duplicate event nodes across multiple media reports, `wiki-scope` cross-references the incoming source against `wiki/index.md` and `wiki/glossary.md`, executes **48-Hour Spatio-Temporal Event Deduplication**, separates candidate primitives into **Events**, **Actors**, **Locations**, **Themes/Timelines**, and **Nodes to Refactor**, and outputs a **Scoped Ingestion Manifest**.

---

## Execution Sequence

### 1. Document & Vault Cross-Referencing
1. Read the target document in `raw/` (or `_input/research/`) using `view_file`.
2. Read `wiki/index.md` and `wiki/glossary.md` to map existing vault topography, Arabic/English aliases, kunyas, and UN OCHA P-Codes (`SD01`–`SD18`).
3. Extract candidate primitives into five distinct pools:
   - **Candidate Events (`wiki/events/`)**: Discrete conflict incidents (`incident`), multi-day military operations (`campaign`), diplomatic talks/agreements (`diplomatic`), or humanitarian emergencies (`crisis`).
   - **Candidate Actors (`wiki/actors/`)**: State forces (`state_force`), paramilitaries/rebel groups/militias (`armed_group`), political coalitions/foreign states (`political_body`), civil society/ERRs/NGOs (`civil_society`), key commanders/leaders (`person`), and media/OSINT outlets (`media_source`).
   - **Candidate Locations (`wiki/locations/`)**: Sudan States (`state_adm1`), Localities (`locality_adm2`), Cities/Towns (`city_town`), Neighborhoods/Sites (`neighborhood_site`), IDP Camps (`idp_camp`), Infrastructure (`infrastructure`), and Border Crossings (`border_crossing`).
   - **Candidate Themes & Timelines (`wiki/themes/`, `wiki/timelines/`)**: Enduring structural drivers ("Why?"), war economy supply chains, military doctrines, or monthly chronological ledgers.
   - **Existing Nodes to Refactor**: Notes already present in `wiki/` where the new source introduces corroborating evidence, updated casualty/displacement counts, shifts in territorial control, or **competing/contradictory narratives**.

### 2. 48-Hour Spatio-Temporal Event Deduplication Rule
Before proposing any **New Event**, verify whether an existing Event note in `wiki/events/` covers the same real-world incident:
$$\lvert t_{\text{valid}}(\text{candidate}) - t_{\text{valid}}(\text{existing}) \rvert \le 48\text{ hours} \quad \land \quad \text{Location}(\text{candidate}) \cap \text{Location}(\text{existing}) \neq \emptyset$$
- **If a match exists**: Do **NOT** create a new Event note. Classify the existing Event note under **Nodes to Refactor** (to append the new source, update casualty ranges, or record competing claims in `## 5. Competing Narratives, Attribution & Contradictions`).
- **If no match exists**: Propose a new canonical Event note named `YYYY-MM-DD <Canonical Event Title>.md` (for discrete incidents) or `<Campaign Title>.md` (for campaigns).

### 3. News & OSINT Significance Filtering
Filter candidate nodes using three qualitative criteria (must score $\ge 0.70$ on composite significance):
- **5W1H Evidentiary Specificity**: Does the candidate event, actor, or location possess concrete spatio-temporal anchoring, identifiable actors, or verifiable impact? (Reject vague background mentions or generic nouns).
- **Network & Causal Interconnectivity**: Can this node connect to $\ge 2$ existing nodes (e.g., linking an incident to its `[[Location]]`, `[[Acting Entities]]`, and parent `[[Campaign]]` or `[[Theme]]`)?
- **Sudan Domain Relevance**: Does the item directly advance intelligence tracking across:
  - Kinetic frontlines, territorial control, and military operations in Sudan.
  - Humanitarian crisis indicators, famine (IPC phases), displacement (IDPs), and civilian protection (ERRs).
  - Political economy (gold, weapons supply chains), regional diplomacy, and foreign sponsorship.
  - OSINT verification, disinformation debunking, and narrative contradiction analysis.

### 4. Generate the Scoped Ingestion Manifest
Output the manifest in standard Markdown format (archived into Section 2 of `wiki/ingestions/YYYY-MM-DD/<source-slug>.md`):

```markdown
### 📋 Scoped Ingestion Manifest: `<source-slug>`
- **Source Medium & Language**: [e.g., Arabic News Article / Telegram Post / Satellite Report] | **Admiralty Rating**: `[e.g., B2]`
- **Target Dynamic Quota**: **E New Events** | **A New Actors** | **L New Locations** | **T New Themes/Timelines** | **K Refactors**

#### 1. Candidate New Events (E)
- `[[YYYY-MM-DD Event Title]]` (`subtype: incident | campaign | crisis | diplomatic`): 1-line 5W1H summary & ACLED category.

#### 2. Candidate New Actors (A)
- `[[Actor Name]]` (`subtype: state_force | armed_group | ...`): Role, affiliation, and ACLED actor type.

#### 3. Candidate New Locations (L)
- `[[Location Name]]` (`pcode: SD...`, `subtype: city_town | ...`): Admin hierarchy and current control status.

#### 4. Candidate New Themes / Timelines (T)
- `[[Theme or Timeline Title]]`: Structural driver ("Why?") or chronological scope.

#### 5. Existing Nodes to Refactor (K)
- `[[Existing Note]]`: Specific update (e.g., merge corroborating source, update casualty range, or add `ATTRIBUTION_CONFLICT` to Section 5 Contradiction Matrix).

#### 6. Workload Execution Strategy
- [Single-thread sequential (Total new nodes ≤ 6) | Map-Reduce parallel subagents (Total new nodes > 6)]
```

### 5. Setting the Dynamic Quota & Interaction Gate
- **Fast-Path**: If Total New Nodes ($E + A + L + T$) $\le 6$, proceed automatically into `wiki-ingest`.
- **Review Gate**: If Total New Nodes ($E + A + L + T$) $> 6$, present the manifest to the user for confirmation before file creation commences.
