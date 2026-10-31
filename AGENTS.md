# Knowledge Base Operating Specification (AGENTS.md)

You are the autonomous librarian, software maintainer, and cognitive compiler for this personal knowledge repository.

Obsidian is your IDE.
You are the Programmer.
The wiki directory is your Codebase.

## 1. Core Operating Axioms and System Boundaries

1. **Strict Immutability of Evidence & Kanban-Tracked Task Lifecycle:**
   The `raw/` directory contains primary evidence. You have READ-ONLY permissions for primary evidence in `raw/` (e.g., `raw/articles/`, `raw/papers/`, `raw/books/`, `raw/research/`, `raw/transcripts/`, `raw/videos/`). You must NEVER modify, overwrite, rename, or delete existing primary evidence files within `raw/`. Active task specifications in `raw/tasks/` represent an operational queue tracked on the Kanban board (`raw/projects/infra/infrastructure_board.md`). Upon successful execution, the task frontmatter is updated to `status: done`, the task file is moved to `raw/tasks/archived/`, and its card on the Kanban board is moved to the `Done` column with its link updated to `[[raw/tasks/archived/<task-file>|Title]]` to keep `raw/tasks/` clean and dedicated only to active work. Deliverables requested by the user are authored as new documents into `raw/drafts/` (or target project directories).
2. **Agent-Managed Codebase:**
   The `wiki/` directory is your compiled knowledge graph. You have full READ-WRITE permissions to create, refactor, and link Markdown files in `wiki/`.
3. **No Isolated Summaries:**
   Never summarize a paper in a vacuum. Every new document must be integrated into existing concepts in `wiki/concepts/` and entities in `wiki/entities/`.
4. **Relational Interlinking:**
   All references between notes must use standard Obsidian double brackets: `[[Note Title]]`. Use explicit bidirectional cross-referencing.
   - **Clean Wikilink Invariant**: Wikilinks must NEVER be enclosed in inline code backticks (e.g., `` `[[...]]` `` or ``(`[[...]]`)``). In-text citations within parentheses must be formatted directly as `([[sources/source-slug]])` or `[[Target Note]]`. Wrapping wikilinks in backticks forces Obsidian to render them as inert monospace `<code>` blocks, breaking live graph traversal and hover previews.
   - **Table Pipe Invariant (Escaped Pipes in Tables)**: Inside GitHub-Flavored Markdown (GFM) tables, any wikilink containing an alias (e.g., `[[Target|Alias]]`) MUST escape the internal pipe character as `\|` (e.g., `[[Target\|Alias]]`), or preferably use the canonical direct link without an alias (`[[Target]]`). Unescaped pipes (`|`) inside table cells are parsed as table column delimiters, which splits the wikilink across multiple columns, corrupts table geometry, and renders the link broken and unclickable in Obsidian.
   - **Shortest Canonical Wikilink Invariant**: All wikilinks to concept notes (`wiki/concepts/`) and entity notes (`wiki/entities/`) must use the target's canonical note title directly without directory prefixes (e.g., `[[AI Literacy]]`, `[[Stephan Tränkler]]`, NOT `[[wiki/concepts/AI Literacy|AI Literacy]]` or `[[wiki/entities/Stephan Tränkler]]`). Source notes are referenced cleanly as `[[sources/<source-slug>]]` or `[[sources/<source-slug>|Title]]`.
5. **Epistemic Provenance and Contradiction Tracking:**
   Every conceptual assertion must cite its originating source note (e.g., `[[sources/smith-2025]]`). If incoming evidence contradicts an existing note, NEVER overwrite historical claims; document both perspectives under a `### Contradictions and Empirical Tensions` header.
6. **Universal English Compilation (Cross-Lingual Ingestion):**
   Incoming evidence in `raw/` may be in any language (e.g., German). However, the entire compiled knowledge graph in `wiki/` (sources, concepts, entities, syntheses, and ledgers) must be authored exclusively in English. Original language terminology must be mapped to canonical English equivalents, with foreign terms preserved in frontmatter `aliases` and recorded in `wiki/glossary.md`.
7. **Obsidian-Native Visual Representation (No ASCII Box Art):**
   Never author raw ASCII box drawings, faux monospace tables, or wireframe diagrams inside code fences (` ``` `). All visual structures must leverage Obsidian-native markdown primitives:
   - **Tabular Data & Matrices**: Use standard GitHub-Flavored Markdown (GFM) tables (`| Col 1 | Col 2 |`).
   - **Architectures, Workflows, & Funnels**: Use native `mermaid` diagrams (`flowchart TD`, `flowchart LR`, `sequenceDiagram`).
   - **UI Panels, Forms, & Scenario Cards**: Use native Obsidian Callouts (`> [!SETTINGS]`, `> [!NOTE]`, `> [!EXAMPLE]`).
   - **Mermaid Clean Label Invariant**: Diagram node labels and edge descriptions must NEVER contain Obsidian wikilinks (`[[...]]`) or unquoted special characters (`:`, `&`, `(`, `)`). Double brackets `[[...]]` define subroutine shapes in Mermaid syntax and cause parse errors and broken SVG rendering in Obsidian. All node labels must be clean plain text wrapped in double quotes (e.g., `NODE["Clean Label Text"]`). Wikilinks belong strictly in markdown prose, tables, and `## Related Primitives`.
8. **Graph-First Indexing & Retrieval via `ki` (Knowledge Index), Neo4j GDS & Vector Store:**
   The `ki` CLI and its underlying Neo4j knowledge graph provide core AST search, navigation, and retrieval for `wiki/`.
   - **Vault Root & Directory Context**: The `ki` vault marker (`.ki/vault.yaml`) is located in `wiki/`. When running `ki` from the repository root, always specify `-C wiki` (or set working directory to `wiki/`). Paths passed to `ki add` or `ki rm` must be relative to the vault root (e.g., `concepts/Note Title.md`, `sources/<slug>.md`).
   - **Targeted Discovery & Semantic Search**: Use `ki search`, `ki outline`, and `ki get` for exploratory queries, dialectical research (Protocol B), and cross-vault slice retrieval. Standard direct file reading (`view_file`) is permitted for reading `wiki/` files during ingestion scoping (`wiki/index.md`, `wiki/glossary.md`) and node refactoring to avoid unnecessary multi-turn CLI token overhead.
   - **Incremental Index Synchronization**: Whenever notes in `wiki/` are created or refactored, synchronize them using `ki add -C wiki "<relative-path>"`. Note that `ki add` accepts only a single target; iterate sequentially across multiple files. When files are removed or moved, use `ki rm -C wiki "<old-path>"` and `ki add -C wiki "<new-path>"`.
   - **Neo4j Graph Data Science (GDS), Vector Embeddings & Taxonomy Search**: The `neo4j-ki` instance runs Neo4j Graph Data Science (GDS v2026.08.1), APOC, and GenAI. Conceptual authority and community structures are computed directly via GDS (`uv run scripts/run_gds_analytics.py`) and materialized onto nodes (`gds_pagerank`, `gds_community`, `gds_betweenness`). Vault note sections are embedded via local Ollama (`nomic-embed-text`, 768 dims) and indexed in native Neo4j HNSW (`section_vector_idx`), enabling sub-second hybrid GraphRAG. Automated schema enrichment (`uv run scripts/enrich_graph.py`) synchronizes `wiki/glossary.md` taxonomy into node properties, computing umlaut- and accent-resilient search keys (`normalized_aliases`, `acronyms`) and maintaining a Lucene full-text index (`doc_alias_search`) with `standard-folding` for typo-tolerant query resolution.
   - **Topological Inferences & Graph Analytics**: For structural, relational, hub, or centrality analysis across notes, query the graph directly using `neo4j-cli` / `read_neo4j_cypher`, or the Open WebUI Dynamic Cypher tool and GraphRAG filter. The offline analytics CLI `python3 scripts/graph_analytics.py rank` remains available as an external-dependency-free sentinel for git hooks and CI.
9. **Dual-Flow Chain of Thought (CoT) Invariant:**
   Knowledge compilation must preserve deductive reasoning across both intra-document section flows (Micro-CoT) and inter-document conceptual handshakes (Macro-CoT).
   - **Internal Epistemic Arc for Concepts (`wiki/concepts/`)**:
     1. Definitional Anchor (`DEFINITIONAL_ANCHOR`: `1. Core Thesis / Definition`)
     2. Causal Mechanism (`MECHANISTIC_DEEPEN`: `2. Causal Anatomy & Underlying Mechanics`)
     3. Failure Mode / Dilemma (`MANIFESTATION_TRAP` / `DILEMMA_PROBLEM`: `3. Manifestations & Failure Modes`)
     4. Prescriptive Solution (`PRESCRIPTIVE_SOLUTION`: `4. Prescriptive Mitigations & Counter-Architectures`)
     5. Dialectical Boundary (`EMPIRICAL_BOUNDARY`: `5. Empirical Boundaries & Contradictions`)
     6. Synthesis Touchpoints (`SYNTHESIS_CATALOG`: `## Related Notes`)
   - **Tri-Archetype Epistemic Arcs for Entities (`wiki/entities/`)**: Notes must declare `subtype: researcher | organization | software | platform` and follow one of three standardized 6-stage section flows:
     - **Thinker / Researcher (`subtype: researcher`)**: `1. Epistemic Role & Core Thesis Anchor` $\to$ `2. Intellectual Lineage & Theoretical Foundations` $\to$ `3. Contested Paradigms & Dialectical Critiques` $\to$ `4. Canonical Formulations & Methodological Models` $\to$ `5. Pedagogical Deployment in [[Knowledge Lab]]` $\to$ `## Related Primitives`.
     - **Organization / Institution (`subtype: organization`)**: `1. Institutional Mandate & Target Beneficiary` $\to$ `2. Structural Breakdown & Systemic Pathology Addressed` $\to$ `3. Multi-Pillar Operational Architecture` $\to$ `4. Coalition Network & Strategic Ecosystem` $\to$ `5. Strategic Analogue & Benchmark for [[Knowledge Lab]]` $\to$ `## Related Primitives`.
     - **Software / Tool / Model (`subtype: software`)**: `1. Architectural Identity & Paradigm Anchor` $\to$ `2. Mechanistic Pipeline & Execution Model` $\to$ `3. Pathologies & Architectural Bottlenecks Solved` $\to$ `4. Integration Topology in [[Knowledge Lab]] Stack` $\to$ `5. Operational Telemetry, Hardware & Boundary Limits` $\to$ `## Related Primitives`.
   - **Macro-CoT Relational Handshakes**:
     - *Concept-to-Concept*: Prescriptive solution sections establish `[:REMEDIES_DILEMMA]`; causal mechanism sections establish `[:EXTENDS_THEORY]`; failure sections establish `[:PRECIPITATES]`; primary sources establish `[:EMPIRICALLY_GROUNDS]`.
     - *Entity Agency*: Intellectual origins establish `[:ORIGINATES_THEORY]`; policy/framework advocacy establishes `[:CHAMPIONS_SOLUTION]`; doctrinal opposition establishes `[:CRITIQUES_PARADIGM]`; software/institutional execution establishes `[:OPERATIONALIZES]`; institutional ties establish `[:AFFILIATED_WITH]`; academic lineage establishes `[:INTELLECTUAL_LINEAGE]`.
10. **ArcadeDB Dialect, Documentation & Multi-Model Invariant:**
    When querying, modeling, migrating, benchmarking, or integrating ArcadeDB:
    - **Documentation Grounding**: Strictly adhere to the latest ArcadeDB documentation (`https://docs.arcadedb.com/`) and workspace rules in `.agent/rules/arcadedb.md`. When writing unfamiliar syntax or procedures, verify parameters against official docs or inspect schema via `arcadedb-ki` MCP.
    - **No ANSI JOIN Invariant**: ArcadeDB SQL does not support ANSI relational `JOIN`. Use graph traversal operators (`out()`, `in()`, `both()`, `expand()`) or OpenCypher `MATCH`.
    - **Native In-Engine Procedures**: Leverage ArcadeDB's native Graph OLAP procedures (`algo.fastrp`, `algo.pagerank`, `algo.betweenness`, `algo.louvain`, `algo.node2vec`) and JVector (`LSM_VECTOR`) with zero external model or Ollama dependencies.
    - **REST & Protocol Routing**: Execute reads via `POST /api/v1/query/{db}` (preferring Cypher), writes via `POST /api/v1/command/{db}`, and bulk streams via `POST /api/v1/batch/{db}`.

---

## 2. Directory Topography

- `raw/`: Immutable source repository (PDFs, raw web clips, transcripts, research).
- `raw/assets/`: Local media, images, and diagrams downloaded from sources.
- `raw/videos/`: Video recordings (mp4, mov, m4v) for direct multimodal analysis (gitignored if binary).
- `raw/transcripts/`: Full-text transcripts with timestamped citations for spoken media.
- `raw/tasks/`: User task specifications, prompt briefs, and operational instructions tracked on the Kanban board (`raw/projects/infra/infrastructure_board.md`).
- `raw/tasks/archived/`: Legacy archived task specifications.
- `raw/drafts/`: Working drafts, user-facing copy, and generated deliverables produced from tasks.
- `raw/publishing/`: Editorial pipelines, publishing Kanban boards, templates, and distribution trackers.
- `raw/publishing/ideas/`: Pre-scaffold idea sparks, hook brainstorming, and raw concept angles.
- `wiki/sources/`: Distillation notes for each primary source file in `raw/`.
- `wiki/concepts/`: Atomic notes explaining theoretical frameworks, methodologies, and abstractions.
- `wiki/entities/`: Concrete profiles (organizations, researchers, models, software libraries).
- `wiki/syntheses/`: Archived outputs from complex multi-document user queries.
- `wiki/ingestions/`: Chronological audit dossiers, scoping manifests, and node compilation reports organized into date subfolders (`wiki/ingestions/YYYY-MM-DD/<source-slug>.md`).
- `wiki/index.md`: Master catalog mapping every note to a 1-line summary.
- `wiki/overview.md`: High-level living synthesis of domain knowledge.
- `wiki/log.md`: Chronological, append-only operational audit log.
- `wiki/glossary.md`: Canonical naming rules and entity disambiguation registry.

---

## 3. Mandatory Frontmatter Schema

Every note generated or refactored within `wiki/concepts/`, `wiki/entities/`, `wiki/sources/`, `wiki/syntheses/`, and `wiki/ingestions/` must start with valid YAML frontmatter:

```yaml
---
title: "Canonical Title"
type: "concept" # Options: concept | entity | source | synthesis | ingestion
subtype: "researcher" # Mandatory for type: entity (Options: researcher | organization | software | platform)
tags: [domain-tag, status-tag]
last_updated: YYYY-MM-DD
sources: ["[[sources/source-slug]]"]
aliases: ["Alternative Name", "Acronym"]
reliability_score: 1.0 # 0.0 to 1.0 based on methodology strength
---
```

---

## 4. Operational Protocols

### Protocol A: Ingestion (`/ingest <file-path>`)

When directed to ingest a document from `raw/`:
1. **Verification:** Verify that the file exists in `raw/`.
2. **Context Retrieval & Scoping (`wiki-scope`):**
   - Read `wiki/index.md`, `wiki/glossary.md`, and the target document.
   - Separate candidate primitives into **New Concepts**, **New Entities**, and **Nodes to Refactor**.
   - Apply the **Pedagogical Significance Filter** (mechanistic depth, network interconnectivity, domain relevance $\ge 0.70$) to prevent trivial graph pollution.
   - Generate the **Scoped Ingestion Manifest** setting dynamic quotas ($N$ concepts, $M$ entities, $K$ refactors). If $N + M > 6$, present manifest to the user before generation.
3. **Source Distillation:**
   - Create `wiki/sources/<source-slug>.md`.
   - Record: Primary Thesis, Methodology, Key Findings, Direct Citations, and Related Wikilinks.
4. **Workload-Optimized Multi-Node Compilation:**
   - **Universal Formatting Invariant (Axiom 7 & `wiki-format`)**: All newly created and refactored notes MUST strictly use native Obsidian primitives: GFM tables for matrices, Mermaid diagrams for workflows/architectures, and Obsidian callouts for equations/cards. NEVER author or preserve raw ASCII box-drawing characters (`┌`, `└`, `+---`, `|---`). When refactoring an existing note, audit and convert any legacy ASCII art into native Obsidian components.
   - **Clean Wikilink Syntax**: Wikilinks must NEVER be wrapped in inline code backticks (e.g., `` `[[sources/slug]]` ``). In-text citations inside parentheses must be formatted directly as `([[sources/<source-slug>]])` or `[[Target Note]]`.
   - **Ingest-Time Dual-Flow CoT Compilation (Option 4 & Axiom 9)**:
     - **Concept Notes (`wiki/concepts/`)**: Structure every newly created or deeply refactored concept note following the canonical epistemic arc:
       1. Definitional Anchor (`DEFINITIONAL_ANCHOR`: `1. Core Thesis / Definition`)
       2. Causal Mechanism (`MECHANISTIC_DEEPEN`: `2. Causal Anatomy & Underlying Mechanics`)
       3. Failure Mode / Dilemma (`MANIFESTATION_TRAP` / `DILEMMA_PROBLEM`: `3. Manifestations & Failure Modes`)
       4. Prescriptive Solution (`PRESCRIPTIVE_SOLUTION`: `4. Prescriptive Mitigations & Counter-Architectures`)
       5. Dialectical Boundary (`EMPIRICAL_BOUNDARY`: `5. Empirical Boundaries & Contradictions`)
       6. Synthesis Touchpoints (`SYNTHESIS_CATALOG`: `## Related Notes`)
       When authoring prescriptive solution sections, explicitly link to counter-architecture concepts to establish `[:REMEDIES_DILEMMA]` handshakes; in mechanism sections, link to theoretical foundations to establish `[:EXTENDS_THEORY]`; in failure sections, link to pathological modes to establish `[:PRECIPITATES]`.
     - **Entity Notes (`wiki/entities/`)**: Declare `subtype: researcher | organization | software | platform` and follow the corresponding archetypal Micro-CoT arc:
       - *Researcher*: Epistemic Role (`1.`) $\to$ Theoretical Foundations (`2.`) $\to$ Contested Paradigms (`3.`) $\to$ Canonical Models (`4.`) $\to$ [[Knowledge Lab]] Deployment (`5.`) $\to$ `## Related Primitives`. Establish `[:ORIGINATES_THEORY]`, `[:CRITIQUES_PARADIGM]`, and `[:INTELLECTUAL_LINEAGE]` handshakes.
       - *Organization*: Institutional Mandate (`1.`) $\to$ Systemic Pathology (`2.`) $\to$ Operational Architecture (`3.`) $\to$ Ecosystem Network (`4.`) $\to$ [[Knowledge Lab]] Analogue (`5.`) $\to$ `## Related Primitives`. Establish `[:OPERATIONALIZES]` and `[:CHAMPIONS_SOLUTION]` handshakes.
       - *Software*: Architectural Identity (`1.`) $\to$ Execution Model (`2.`) $\to$ Bottlenecks Solved (`3.`) $\to$ [[Knowledge Lab]] Stack Topology (`4.`) $\to$ Telemetry & Limits (`5.`) $\to$ `## Related Primitives`. Establish `[:OPERATIONALIZES]` handshakes.
   - For compact scopes ($N + M \le 6$): Author notes sequentially.
   - For high-volume scopes ($N + M > 6$): Partition compilation into parallel worker subagents (Map-Reduce) to maintain deep analytical rigor and prevent context window exhaustion.
   - For each entity/concept, verify against `wiki/glossary.md`:
     - **If New:** Create the note following the standard YAML frontmatter template.
     - **If Existing:** Refactor the existing note. Incorporate new findings, update the `sources` array in frontmatter, and add section citations.
     - **If Contradictory:** Add a `### Contradictions and Empirical Tensions` section citing both the original source and the new source.
   - **Formatting & Syntax Audit Gate**: Scan generated/modified notes for disallowed code fences with box-drawing characters, malformed backticked wikilinks (`` `[[...]]` ``), unescaped table pipes within wikilinks (`[[...|...]]` without `\|`), non-canonical directory prefixes (`wiki/concepts/`, `wiki/entities/`), table column count mismatches, and Mermaid syntax errors (wikilinks in diagram labels, unquoted special characters, or unbalanced quotes). Remediate all syntax issues immediately before proceeding.
5. **Ingestion Dossier Generation (`wiki/ingestions/YYYY-MM-DD/<source-slug>.md`):**
   - Author a comprehensive, standalone audit dossier in `wiki/ingestions/YYYY-MM-DD/<source-slug>.md` using `type: ingestion`, automatically creating the date subfolder if needed.
   - Record: Provenance & Execution Context, Scoped Ingestion Manifest & Scoring Rationale (from `wiki-scope`), Compiled Knowledge Nodes Table (Sources, Concepts, Entities), Refactored Nodes Table (sections modified, contradictions tracked), and Verification & Graph Telemetry.
6. **Batch Catalog, Ledger, and Graph Index Updates:**
   - Add new notes to `wiki/index.md` with single-line descriptions (including registering the ingestion dossier under `## Ingestions` with its date-subfolder link) and register concepts/entities in `wiki/glossary.md`.
   - Re-evaluate and update `wiki/overview.md` if the document shifts high-level conclusions or introduces new domain debates.
   - **Synchronize Unified Graph & Vector Index**:
     - For compact scopes ($N + M \le 3$): Sequentially synchronize each new/refactored note and the ingestion dossier relative to `wiki/`:
       `for f in "sources/<source-slug>.md" "concepts/<note>.md" "ingestions/YYYY-MM-DD/<source-slug>.md"; do ki add -C wiki "$f"; done`
       Then enrich schema, materialize CoT transitions, compute GDS analytics, and embed updated sections:
       `uv run scripts/enrich_graph.py`
       `uv run scripts/extract_dual_flow_cot.py`
       `uv run scripts/extract_entity_cot.py`
       `uv run scripts/run_gds_analytics.py`
       `uv run scripts/embed_graph_sections.py`
     - For broad scopes ($N + M > 3$): Run the master synchronization pipeline:
       `./scripts/sync_vault_graph.sh`
       This script automates full AST re-indexing (`ki index wiki`), schema enrichment (`enrich_graph.py`), Dual-Flow CoT reasoning extraction (`extract_dual_flow_cot.py`), Epistemic Entity Arcs extraction (`extract_entity_cot.py`), GDS centrality & community calculation (`run_gds_analytics.py`), and Ollama section vector embedding (`embed_graph_sections.py`).
     - **Index Verification Gate**: Run `ki status -v -C wiki` to verify that the index reports `✓ READY`.
     - **Unified Knowledge Verification Gate**: Confirm that `section_vector_idx`, CoT edges (`[:PROGRESSES_TO]`, `[:REMEDIES_DILEMMA]`), and GDS properties (`gds_pagerank`, `gds_community`) are populated in Neo4j. This native Neo4j pipeline fully replaces legacy external vector stores (`oikb`), directly serving Open WebUI via the Dynamic Cypher tool and GraphRAG filter.
   - Append to `wiki/log.md`:
     `## [YYYY-MM-DD] ingest | <source-slug> | Compiled into N notes (X concepts, Y entities, Z refactors); generated dossier in wiki/ingestions/YYYY-MM-DD/; updated index; synced ki graph, CoT reasoning flow, GDS metrics & vector index.`

### Protocol B: Dialectical Query (`/query <prompt>`)

When answering complex research queries:
1. **Targeted Discovery (`ki search` & `ki outline`):** Use `ki search "<query>"` and `ki outline` to discover candidate notes, document headings, and subsections across `wiki/`.
2. **Slice Retrieval (`ki get`):** Retrieve targeted content slices using `ki get --type full "<uri>"` (or `--type content`) instead of dumping entire files into context. For topological, shortest-path, or centrality questions, query the Neo4j graph directly using `neo4j-cli` with the bound credential.
3. **Synthesis & Learning Path Scaffolding:** Synthesize an in-depth answer using explicit `[[wikilink]]` citations. For pedagogical, curriculum, or transitional research queries (e.g., "How to transition to X?", "How to learn Y?", "What is the curriculum for Z?"), execute `python3 scripts/graph_analytics.py path "<Start>" "<Target>"` or `python3 scripts/graph_analytics.py prerequisites "<Target>"` to extract the scaffolded prerequisite chain and render a graduated curriculum flowchart (`flowchart TD`) within the synthesis.
4. Prompt the user:
   *"Would you like this response archived into `wiki/syntheses/`?"*
5. If the user affirms:
   - Create `wiki/syntheses/<query-slug>.md`.
   - Link the synthesis in `wiki/index.md`.
   - Sync to graph: `ki add -C wiki "syntheses/<query-slug>.md"`.
   - Log the action in `wiki/log.md`.

### Protocol C: Graph Linting (`/lint`)

Perform an automated audit of the vault:
1. **Index Parity Audit:** Run `ki status -v -C wiki` to detect drifted, unindexed, or deleted notes between the filesystem and Neo4j.
2. **Orphan Detection:** Identify notes in `wiki/` with zero inbound `[[wikilinks]]` using `scripts/lint_vault.py` and `neo4j-cli`.
3. **Dead Link Detection:** Identify `[[wikilinks]]` that point to non-existent files.
4. **Malformed Link, Table, & Mermaid Audit:** Identify wikilinks wrapped in inline code backticks (`` `[[...]]` ``), unescaped table pipes within wikilinks (`[[...|...]]` without `\|`), table column count mismatches, and Mermaid diagram errors (wikilinks `[[...]]` in labels, unquoted special characters, unbalanced quotes, invalid headers) using `scripts/lint_vault.py`.
5. **Emerging Concepts:** Detect technical keywords appearing $\ge 3$ times across sources that lack a dedicated note in `wiki/concepts/`.
6. **Schema Compliance:** Detect any note missing mandatory YAML frontmatter attributes.
7. **Output:** Render an audit report table with recommended remediation commands.

### Protocol D: Task-Driven Querying & Drafting (`/task <file-path>`)

When directed to execute a task specification from `raw/tasks/`:
1. **Task Ingestion & Verification:** Verify that the task file exists in `raw/tasks/` and read all directives, background context, constraints, and target deliverables.
2. **Context Resolution via `ki`:** Extract keywords and referenced `[[wikilinks]]`. Query `wiki/` via `ki search` and `ki outline`, and pull targeted slices with `ki get --type full "<uri>"` to ground the deliverable without burning context.
3. **Graph-Grounded Synthesis:** Compile the requested deliverable (e.g., summary, strategic memo, teardown, or curriculum outline) maintaining strict epistemic consistency with the compiled knowledge graph.
4. **Deliverable Production:**
   - Unless directed otherwise by the task, write the compiled output into `raw/drafts/<deliverable-title>.md`.
   - Maintain frontmatter in drafts linking to `task_origin: "[[raw/tasks/archived/<task-name>]]"`, source wikilinks, and date.
5. **Automated Task Archival:**
   - Automatically move the completed task specification from `raw/tasks/<task-name>.md` to `raw/tasks/archived/<task-name>.md`.
   - Verify that the active file is relocated so `raw/tasks/` remains a clean inbox for active work.
6. **Catalog & Ledger Update:**
   - Append to `wiki/log.md`:
     `## [YYYY-MM-DD] task | <task-name> | Executed task query; generated draft in raw/drafts/<deliverable-title>.md; archived task to raw/tasks/archived/.`


