---
name: wiki-ingest
description: Compiles unorganized documents, transcripts, PDFs, and videos from raw/ into atomic Obsidian wiki notes using dynamic pre-scoping and optimized workload pipelines.
---

# Wiki Ingest Skill

## Objective
Ingest uncompiled primary evidence from `raw/` (Markdown notes, research dossiers, web articles, PDFs, transcripts, and video recordings), dynamically scope conceptual primitives via `wiki-scope`, compile atomic notes across `wiki/concepts/` and `wiki/entities/`, refactor existing knowledge, and maintain vault indices.

---

## Supported Source Types & Parsing Procedures

### 1. Markdown & Text Clippings (`raw/articles/`, `raw/notes/`, `raw/research/`)
- Read directly via standard file viewer.

### 2. PDF Documents (`raw/projects/`, `raw/papers/`, `raw/books/`)
- Extract text using the installed `pypdf` parser:
  ```bash
  python3 -c "import pypdf; reader=pypdf.PdfReader('raw/path/to/doc.pdf'); print('\n'.join([p.extract_text() or '' for p in reader.pages]))" > /tmp/parsed_source.txt
  ```

### 3. Spoken Transcripts (`raw/transcripts/`)
- Read full markdown/vtt/srt transcript directly.
- Preserve temporal timestamps (e.g., `[04:15]`) in citations inside the distillation note.

### 4. Direct Multimodal Video Files (`raw/videos/`, `raw/assets/videos/`)
- **File size < 100 MB**: Ingest directly using the multimodal binary `view_file` tool.
  - Analyze both spoken audio and on-screen visual presentation slides, software demos, and diagrams.
  - Record key visual diagrams or slide timestamps in the distillation note.
- **File size ≥ 100 MB**: Advise the user to extract or provide the transcript in `raw/transcripts/<slug>.md` (e.g. via MacWhisper, YouTube transcript, or local whisper) to avoid binary size limits and repository bloat.

---

## Execution Sequence

### 1. Path & Immutability Verification
- Confirm the target file is inside `raw/`.
- Never modify, rename, or delete any file in `raw/`.

### 2. Pre-Ingestion Scoping (`wiki-scope`)
- Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
- Run the `wiki-scope` protocol to filter candidate primitives by pedagogical significance ($\ge 0.70$).
- Output the **Scoped Ingestion Manifest** setting the dynamic quotas:
  - **$N$ New Concepts**
  - **$M$ New Entities**
  - **$K$ Nodes to Refactor**
- **Gating**: If $N + M \le 6$, proceed automatically. If $N + M > 6$, present the manifest to the user before generating notes.

### 3. Cross-Lingual Normalization (Axiom 6)
- If the source is in another language (e.g., German), translate and compile all syntheses, concepts, and entities exclusively in **English**.
- Preserve original foreign terms in frontmatter `aliases` and register canonical mappings in `wiki/glossary.md`.

### 4. Source Distillation (`wiki/sources/<source-slug>.md`)
- Create standard YAML frontmatter (`title`, `type: source`, `tags`, `last_updated`, `sources`, `reliability_score`).
- Record: Primary Thesis, Methodology / Context, Key Findings (with page or timestamp citations), Direct Quotes, and Related Concepts/Entities.

### 5. Multi-Node Compilation & Workload Optimization

#### Universal Formatting Invariant (MANDATORY across all compilation & refactors)
- **Zero ASCII Box Art (Axiom 7 & `wiki-format`)**: NEVER author or preserve raw ASCII box-drawing characters (`┌`, `└`, `├`, `│`, `+---+`, `|`, `+===+`) inside code fences (` ``` `).
- **Clean Wikilinks (Axiom 4)**: NEVER author or wrap `[[wikilinks]]` in inline code backticks (e.g., `` `[[sources/slug]]` `` or ``(`[[sources/slug]]`)``). In-text citations must always be formatted cleanly as `([[sources/slug]])` or `[[Concept Name]]`. Backticks force Obsidian to render them as inert monospace `<code>` elements, breaking hover previews and graph indexing.
- **Table Pipe Invariant (Escaped Pipes in Tables)**: Within GitHub-Flavored Markdown (GFM) tables, vertical pipes (`|`) serve as column delimiters. Therefore, any wikilink with an alias inside a table cell MUST escape the pipe character as `\|` (e.g., `| [[Target\|Display Text]] |`) or use canonical unaliased wikilinks `[[Target]]`. An unescaped pipe (e.g., `| [[Target|Display Text]] |`) breaks table syntax, splits the wikilink across multiple table columns, and prevents Obsidian from parsing the link.
- **Canonical Shortest Wikilink Invariant**: All wikilinks to concepts and entities in `wiki/` must use direct note titles without redundant directory prefixes (e.g., use `[[Concept Name]]` or `[[Entity Name]]`, NEVER `[[wiki/concepts/...]]` or `[[wiki/entities/...]]`). Source distillations should be linked using the standard canonical prefix `[[sources/<source-slug>]]`.
- **Dual-Flow Chain of Thought Invariant (Axiom 9 & Option 4)**:
  - **Concept Notes (`wiki/concepts/`)**: Every compiled or refactored concept note in `wiki/concepts/` must follow an explicit, graduated reasoning progression using canonical heading anchors:
    1. Definitional Anchor (`DEFINITIONAL_ANCHOR`: `1. Core Thesis / Definition`)
    2. Causal Mechanism (`MECHANISTIC_DEEPEN`: `2. Causal Anatomy & Underlying Mechanics`)
    3. Failure Mode / Dilemma (`MANIFESTATION_TRAP` / `DILEMMA_PROBLEM`: `3. Manifestations & Failure Modes`)
    4. Prescriptive Solution (`PRESCRIPTIVE_SOLUTION`: `4. Prescriptive Mitigations & Counter-Architectures`)
    5. Dialectical Boundary (`EMPIRICAL_BOUNDARY`: `5. Empirical Boundaries & Contradictions`)
    6. Synthesis Touchpoints (`SYNTHESIS_CATALOG`: `## Related Notes`)
    When authoring prescriptive solution sections, explicitly link to counter-architecture concepts to establish `[:REMEDIES_DILEMMA]` handshakes; in mechanism sections, link to foundational concepts to establish `[:EXTENDS_THEORY]`; in failure sections, link to pathological modes to establish `[:PRECIPITATES]`.
  - **Entity Notes (`wiki/entities/`)**: Declare `subtype: researcher | organization | software | platform` and follow the corresponding archetypal Micro-CoT arc:
    - *Researcher (`subtype: researcher`)*: Epistemic Role (`1.`) $\to$ Theoretical Foundations (`2.`) $\to$ Contested Paradigms (`3.`) $\to$ Canonical Models (`4.`) $\to$ [[Knowledge Lab]] Deployment (`5.`) $\to$ `## Related Primitives`. Establish `[:ORIGINATES_THEORY]`, `[:CRITIQUES_PARADIGM]`, and `[:INTELLECTUAL_LINEAGE]` handshakes.
    - *Organization (`subtype: organization`)*: Institutional Mandate (`1.`) $\to$ Systemic Pathology (`2.`) $\to$ Operational Architecture (`3.`) $\to$ Ecosystem Network (`4.`) $\to$ [[Knowledge Lab]] Analogue (`5.`) $\to$ `## Related Primitives`. Establish `[:OPERATIONALIZES]` and `[:CHAMPIONS_SOLUTION]` handshakes.
    - *Software (`subtype: software`)*: Architectural Identity (`1.`) $\to$ Execution Model (`2.`) $\to$ Bottlenecks Solved (`3.`) $\to$ [[Knowledge Lab]] Stack Topology (`4.`) $\to$ Telemetry & Limits (`5.`) $\to$ `## Related Primitives`. Establish `[:OPERATIONALIZES]` handshakes.
- **Tabular Data & Matrices**: Convert to standard GitHub-Flavored Markdown (GFM) tables (`| Col 1 | Col 2 |`).
- **Architectures, Workflows, & Funnels**: Convert to native `mermaid` diagrams (`flowchart TD`, `flowchart LR`, `sequenceDiagram`).
- **Equations, Equations Panels, & UI Cards**: Convert to Obsidian Callouts (`> [!NOTE]`, `> [!SETTINGS]`, `> [!EXAMPLE]`) with LaTeX math blocks (`$$...$$`).
- **Refactoring Sanity Rule**: When refactoring an existing note, ALWAYS audit and convert any legacy ASCII tables or box art in that note into native Obsidian components.

#### Execution Workflows
Compile the dynamic manifest using one of two execution paths:
- **Small Workload ($N + M \le 6$)**: Compile notes sequentially within the primary agent session, strictly enforcing the Universal Formatting Invariant on every new and refactored note.
- **High-Volume Workload ($N + M > 6$)**: Execute **Map-Reduce Parallelization**:
  1. **Map**: Invoke 2–3 parallel subagents using `invoke_subagent` (type `self`), partitioning the manifest:
     - Worker 1: Compiles Concepts Batch A.
     - Worker 2: Compiles Concepts Batch B.
     - Worker 3: Compiles Entities & executes Refactors.
  2. Each worker authors atomic Markdown files following the mandatory frontmatter schema, internal mechanisms, bidirectional `[[wikilinks]]`, and the Universal Formatting Invariant.
  3. **Reduce**: The parent agent verifies completed files, conducts a formatting audit, and performs atomic ledger consolidation.

#### Formatting Audit & Validation Gate
Before proceeding to catalog and ledger updates, validate all newly created and refactored files:
1. Scan for disallowed code fences containing `┌`, `└`, `+---`, `|---`, or text box borders.
2. Scan for malformed backticked wikilinks (`` `[[...]]` ``). If detected, strip backticks immediately.
3. Scan table rows (`| ... |`) for unescaped pipes inside wikilinks (`\[\[[^\]\n]*?(?<!\\)\|[^\]\n]*?\]\]`). If found, escape them as `\|`.
4. Check for non-canonical path prefixes in concept/entity links (`[[wiki/concepts/...]]` or `[[wiki/entities/...]]`) and strip `wiki/concepts/` or `wiki/entities/`.
5. Run `python3 scripts/lint_vault.py` to ensure zero graph or formatting errors before index synchronization.

### 6. Ingestion Summary Dossier Generation (`wiki/ingestions/YYYY-MM-DD/<source-slug>.md`)
- Author a dedicated, comprehensive audit report in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` (creating the `YYYY-MM-DD/` date subfolder if it does not already exist).
- **Mandatory Frontmatter**:
  ```yaml
  ---
  title: "Ingestion: <source-slug>"
  type: "ingestion"
  tags: [ingestion, audit]
  date: YYYY-MM-DD
  source: "[[sources/<source-slug>]]"
  concepts_created:
    - "[[concepts/Concept Name]]"
  entities_created:
    - "[[entities/Entity Name]]"
  nodes_refactored:
    - "[[concepts/Refactored Note]]"
  ---
  ```
- **Required Sections**:
  1. **Provenance & Execution Context**: Origin file in `raw/`, source distillation link, date, compiler session, workload strategy.
  2. **Scoped Ingestion Manifest & Scoring**: Composite pedagogical significance score ($\ge 0.70$), dynamic quotas ($N, M, K$), and candidate primitive evaluation table.
  3. **Compiled Knowledge Nodes**: GFM table listing Source, Concepts, and Entities with 1-line mechanistic summaries.
  4. **Refactored Nodes & Epistemic Evolution**: GFM table detailing modified sections, empirical updates, and contradiction tracking.
  5. **Verification & Graph Telemetry**: Formatting audit (0 ASCII box art, zero backticked wikilinks), `ki status` reporting, and vault linter output.

### 7. Batch Catalog, Ledger & Graph Synchronization
- Register new concepts and entities in `wiki/glossary.md`.
- Add all newly created notes with 1-line summaries to `wiki/index.md` (including registering the ingestion dossier under `## Ingestions`).
- Re-evaluate and update `wiki/overview.md` if high-level paradigm insights or debates have shifted.
- **Synchronize Unified Graph & Vector Index**:
  - The `ki` vault marker is at `wiki/.ki/vault.yaml`. When executing from the repository root, always use `-C wiki` with relative paths inside `wiki/`.
  - For small updates ($\le 3$ files): Run `ki add -C wiki "<relative-path>"` sequentially for each file (e.g., `for f in "sources/<source-slug>.md" "concepts/<note>.md" "ingestions/YYYY-MM-DD/<source-slug>.md"; do ki add -C wiki "$f"; done`). Note that `ki add` takes only ONE target at a time.
    Follow with graph enrichment, CoT reasoning flow extraction, and embeddings:
    `uv run scripts/enrich_graph.py`
    `uv run scripts/extract_dual_flow_cot.py`
    `uv run scripts/extract_entity_cot.py`
    `uv run scripts/run_gds_analytics.py`
    `uv run scripts/embed_graph_sections.py`
  - For larger updates or batch refactors ($> 3$ files): Run the master pipeline:
    `./scripts/sync_vault_graph.sh`
    This performs full AST re-indexing (`ki index wiki`), schema enrichment (`enrich_graph.py`), Dual-Flow CoT reasoning extraction (`extract_dual_flow_cot.py`), Epistemic Entity Arcs extraction (`extract_entity_cot.py`), GDS centrality & community calculation (`run_gds_analytics.py`), and Ollama section vector embedding (`embed_graph_sections.py`).
  - **Verification Gate**: Run `ki status -v -C wiki` to verify that the index reports `✓ READY`.
  - **Unified Knowledge Verification Gate**: Confirm that `section_vector_idx`, CoT edges (`[:PROGRESSES_TO]`, `[:REMEDIES_DILEMMA]`), and GDS properties (`gds_pagerank`, `gds_community`) are populated in Neo4j. This native Neo4j pipeline fully replaces legacy external vector stores (`oikb`), directly serving Open WebUI via the Dynamic Cypher tool and GraphRAG filter.
- Append to `wiki/log.md`:
  `## [YYYY-MM-DD] ingest | <source-slug> | Compiled into N notes (X concepts, Y entities, Z refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index; synced ki graph, GDS metrics & vector index.`
