---
name: web-deep-research
description: Conducts multi-angle deep web and OSINT research on a specific Sudan conflict event, actor, location, or theme and compiles a structured research dossier into _input/research/ (or raw/reports/). Use whenever the user asks to research, explore the web, or investigate sources for a topic.
---

# Web Deep Research Skill (`web-deep-research`)

## Objective
Execute thorough, multi-perspective web and open-source intelligence (OSINT) research on a specified Sudan conflict event, armed/political actor, geopolitical location, or structural theme, and compile the synthesized findings into a permanent primary evidence dossier saved to `_input/research/<slug>.md` (or `raw/reports/<slug>.md` when designated as primary conflict evidence).

---

## Execution Sequence

### 1. Scope Formulation & Query Decomposition
Break the topic into at least 4 distinct inquiry angles:
- **5W1H & Chronological Reconstruction**: What happened, exact dates/times ($t_{\text{valid}}$ vs. $t_{\text{reported}}$), UN OCHA locations (`pcode`), and acting entities.
- **Empirical & Forensic OSINT Evidence**: Satellite imagery analyses (Yale HRL, Sudan Witness), ACLED data, medical/hospital ledgers, and UN OCHA / IPC humanitarian telemetry.
- **Competing Narratives & Contradictions (GRaSP Model)**: Contrasting claims across SAF-aligned media, RSF channels, independent Sudanese journalism (Radio Dabanga, Sudan Tribune, Sudan War Monitor, Mada Masr), and local Emergency Response Rooms (ERRs).
- **Structural Drivers ("Why?") & Regional Context**: Supply chains (gold, weapons), territorial logistics, ethnic/communal dynamics, and diplomatic/foreign state involvement.

### 2. Multi-Step Multilingual Web Exploration
- Formulate targeted search queries covering each angle.
- Query in both **English and Arabic** (and French where relevant for Chad/Sahel border dynamics) to capture primary regional reporting alongside international coverage.
- Grade each discovered source using the **NATO Admiralty Scale (`A–F` × `1–6`)**.

### 3. Vault Contextual Alignment
- Inspect `wiki/index.md` and `wiki/glossary.md` to identify existing related Event, Actor, Location, or Theme notes and ensure canonical naming.

### 4. Dossier Construction & Formatting
Compile findings into a Markdown document adhering to this structure:
```markdown
# [Title: Canonical Topic & Subtitle]

- **Research Subject**: Intelligence & OSINT deep-dive for [[Target Note]]
- **Target File**: `_input/research/<topic-slug>.md`
- **Date**: YYYY-MM-DD
- **Admiralty Assessment**: `[e.g., B2]`
- **Keywords**: [Comma-separated English & Arabic search keywords]

---

## 1. Executive 5W1H Summary
[High-level overview of What, When, Where, Who, Why, and verification status]

## 2. Chronological Sequence & Operational Mechanics
[Timeline of events, actors involved, tactical mechanics, and territorial shifts]

## 3. Empirical, Humanitarian & Geospatial Findings
[Casualty ranges, displacement data, satellite/OSINT verification, and infrastructure impact]

## 4. Competing Narratives, Attribution & Contradictions
[Side-by-side comparison of conflicting claims across belligerents, local monitors, and OSINT labs]

## 5. Connections to Sudan News Graph (`wiki/`)
[Explicit mapping to existing `wiki/events/`, `wiki/actors/`, `wiki/locations/`, and `wiki/themes/` nodes]

## 6. Primary References & Source Provenance (with Admiralty Ratings)
[Numbered list of sources, author/outlet attributions, Admiralty codes, original languages, and URLs]
```

### 5. File Persistence & Verification
1. Write the compiled dossier to `_input/research/<topic-slug>.md`.
2. If the research was initiated from an active brief in `_input/tasks/<task-slug>.md`, move that task file to `_input/tasks/archived/<task-slug>.md` and update `_input/projects/infra/infrastructure_board.md`.
3. Inform the user and suggest immediate compilation via:
   `/ingest _input/research/<topic-slug>.md`
