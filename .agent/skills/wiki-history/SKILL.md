---
name: wiki-history
description: Queries the epistemic evolution, contradiction history, and chronological touchpoints of any event, actor, location, or theme across wiki/ingestions/ dossiers using scripts/node_history.py and outputs a formatted Markdown report.
---

# Wiki History Skill (`wiki-history`)

## Objective
Trace how an Event, Actor, Location, or Theme originated and evolved across chronological ingestion dossiers in `wiki/ingestions/`.

Extract and synthesize:
1. Initial creation date, originating source distillation (`wiki/sources/`), and initial 5W1H / Admiralty scope.
2. Every subsequent refactor, modified section, casualty/control update, and link addition.
3. Emerging narrative contradictions (`ATTRIBUTION_CONFLICT`, `MAGNITUDE_DISCREPANCY`, `CONTROL_DISPUTE`), OSINT corroborations, or debunks over time.

---

## Execution Sequence

### 1. Identify Target Node
- Confirm the target Event, Actor, Location, or Theme title (case-insensitive substring match).
- If exploring or uncertain of naming, run the node index to check touchpoint density:
  ```bash
  python3 scripts/node_history.py --list
  ```

### 2. Extract Ingestion History via CLI
- Extract the raw chronological timeline from `wiki/ingestions/`:
  - **For Markdown Table export**:
    ```bash
    python3 scripts/node_history.py "<Node Name>" --format markdown
    ```
  - **For deep analytical synthesis**:
    ```bash
    python3 scripts/node_history.py "<Node Name>" --format json
    ```

### 3. Epistemic Evolution Synthesis
When authoring a standalone epistemic report, compile a structured synthesis with the following components:

#### A. Mandatory Frontmatter
```yaml
---
title: "Epistemic Evolution: <Node Name>"
type: "synthesis"
tags: [evolution, synthesis, audit, epistemic-history]
last_updated: YYYY-MM-DD
node_target: "[[<Node Name>]]"
sources:
  - "[[sources/source-1]]"
  - "[[sources/source-2]]"
reliability_score: 0.95
---
```

#### B. Required Sections
1. **Provenance & Historical Footprint**:
   - First recorded date, originating source document, and total touchpoints ($C$ creations + $R$ refactors).
2. **Chronological Evolution Matrix**:
   - GFM table detailing: Date, Operation (`🌱 Created` vs `🔄 Refactored`), Ingestion Dossier, Section(s) Modified, and Epistemic Updates.
3. **Narrative & Verification Trajectory**:
   - Trace how the event or actor profile evolved from initial breaking reports (`single_source`) to corroborated or contested status (`corroborated_with_contradictions` / `confirmed`).
4. **Contradictions & Competing Claims Tracked**:
   - Detail any competing belligerent claims, casualty revisions, or OSINT/satellite debunks introduced across sources.

---

### 4. Output Destination & Persistence

1. **Standalone Synthesis (Default)**:
   - Save to `wiki/syntheses/<node-slug>-epistemic-evolution.md`.
   - Register under `## Syntheses` in `wiki/index.md`.
   - Synchronize with the knowledge graph:
     ```bash
     ki add -C wiki "syntheses/<node-slug>-epistemic-evolution.md"
     ```

2. **Embedded in Domain Note**:
   - When requested to enrich the note directly, append to `wiki/{events,actors,locations,themes}/<Node Name>.md` under `## 📜 Epistemic Evolution & Ingestion History` and sync via `ki add`.

3. **Task Deliverable**:
   - If requested via a task specification in `_input/tasks/`, write to `_input/drafts/<node-slug>-evolution.md` following `wiki-task` protocol.

---

### 5. Audit Logging
Append the completed trace action to `wiki/log.md`:
```markdown
## [YYYY-MM-DD] history | <node-slug> | Compiled epistemic evolution report across N dossiers; saved to <target-path>; synced ki graph.
```
