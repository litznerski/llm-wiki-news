---
name: wiki-history
description: Queries the epistemic evolution and chronological touchpoints of any concept or entity across wiki/ingestions/ dossiers using scripts/node_history.py and outputs a formatted Markdown report.
---

# Wiki History Skill (`wiki-history`)

## Objective
Trace how a theoretical framework, cognitive mechanism, or entity originated and evolved across chronological ingestion dossiers in `wiki/ingestions/`. 

Extract and synthesize:
1. Initial creation date, originating source distillation, and initial conceptual scope.
2. Every subsequent refactor, modified section, empirical update, and link addition.
3. Emerging contradictions, paradigm shifts, or institutional applications over time.

---

## Execution Sequence

### 1. Identify Target Node
- Confirm the target concept or entity title (case-insensitive substring match).
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
node_target: "[[concepts/<Node Name>]]" # or entities/
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
   - GFM table detailing: Date, Event (`🌱 Created` vs `🔄 Refactored`), Ingestion Dossier, Section(s) Modified, and Epistemic Updates.
3. **Dialectical Evolution & Inflection Points**:
   - Qualitative analysis of how the concept transformed over time.
   - Trace the trajectory: e.g., initial definition $\rightarrow$ empirical validation $\rightarrow$ institutional friction $\rightarrow$ counter-architectures.
4. **Contradictions & Theoretical Tensions Tracked**:
   - Note any opposing findings, boundary conditions, or empirical disputes introduced by incoming sources.

---

### 4. Output Destination & Persistence

Determine destination based on user directive:

1. **Standalone Synthesis (Default)**:
   - Save to `wiki/syntheses/<node-slug>-epistemic-evolution.md`.
   - Register under `## Syntheses` in `wiki/index.md`:
     `- [[wiki/syntheses/<node-slug>-epistemic-evolution|<Node Name> Evolution]]: (YYYY-MM-DD) Epistemic trace across N ingestion dossiers.`
   - Synchronize with the knowledge graph:
     ```bash
     ki add -C wiki "syntheses/<node-slug>-epistemic-evolution.md"
     ```

2. **Embedded in Concept/Entity Note**:
   - When requested to enrich the concept directly, append to `wiki/concepts/<Node Name>.md` (or `wiki/entities/`) under:
     `## 📜 Epistemic Evolution & Ingestion History`
   - Paste the GFM evolution table and brief narrative.
   - Synchronize note:
     ```bash
     ki add -C wiki "concepts/<Node Name>.md"
     ```

3. **Task Deliverable**:
   - If requested via a task specification in `raw/tasks/`, write to `raw/drafts/<node-slug>-evolution.md` following `wiki-task` protocol.

---

### 5. Formatting & Clean Link Invariant Gate

- **Zero ASCII Box Art (Axiom 7 & `wiki-format`)**: All matrices must use standard GFM tables (`| Col 1 | Col 2 |`). Workflow timelines must use native Mermaid diagrams (`flowchart TD` or `sequenceDiagram`).
- **Clean Wikilinks Invariant (Axiom 4)**: Wikilinks must NEVER be enclosed in code backticks (e.g. `` `[[...]]` ``). In-text parenthetical citations must be formatted directly as `([[sources/<source-slug>]])` or `[[Target Note]]`.

---

### 6. Audit Logging

Append the completed trace action to `wiki/log.md`:
```markdown
## [YYYY-MM-DD] history | <node-slug> | Compiled epistemic evolution report across N dossiers; saved to <target-path>; synced ki graph.
```
