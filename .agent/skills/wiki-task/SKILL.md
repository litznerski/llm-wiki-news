---
name: wiki-task
description: Executes task specifications from _input/tasks/, resolves context against the Sudan News knowledge graph, drafts deliverables into _input/drafts/, updates task frontmatter to status done, and moves the task card to Done on the Kanban board.
---

# Wiki Task Skill (`wiki-task`)

## Objective
Execute task specifications and intelligence briefs placed into `_input/tasks/`, ground deliverables in the compiled Sudan News & OSINT knowledge graph (`wiki/`), author structured outputs into `_input/drafts/` (or target project directories), update the task file's frontmatter to `status: "done"`, archive it into `_input/tasks/archived/`, and **move the task card to the `Done` column** on the Kanban board (`_input/projects/infra/infrastructure_board.md`).

---

## Execution Sequence

### 1. Task Ingestion & Verification
- Confirm the target task file exists in `_input/tasks/`.
- Read and extract:
  - User directives and target deliverables.
  - Background context, geographic/temporal scope, and constraints.
  - Specific intelligence questions, comparative frameworks, or audiences.
- Update the task card on `_input/projects/infra/infrastructure_board.md` to `## ⚡ In Progress` (if not already there).

### 2. Context Resolution & Vault Grounding via `ki`
- Cross-reference keywords and explicit `[[wikilinks]]` using `ki search "<term>"`, `ki outline`, `wiki/index.md`, and `wiki/glossary.md`.
- Retrieve targeted content slices using `ki get --type full "<uri>"` (or `--type content`) instead of dumping full files into context.
- Maintain strict epistemic consistency with compiled events (`wiki/events/`), actors (`wiki/actors/`), locations (`wiki/locations/`), themes (`wiki/themes/`), NATO Admiralty ratings, and tracked contradictions.

### 3. Deliverable Production
- Author the deliverable in `_input/drafts/<deliverable-title>.md` (or the destination specified in the task brief).
- Ensure mandatory frontmatter is included:
  ```yaml
  ---
  title: "Deliverable Title"
  task_origin: "[[_input/tasks/archived/<task-slug>.md]]"
  sources: ["[[sources/source-slug]]", "[[Event or Actor Title]]"]
  date: YYYY-MM-DD
  ---
  ```
- Structure the content using Obsidian-native primitives (GFM tables, Mermaid diagrams, and Obsidian callouts per `wiki-format`). Never use raw ASCII art boxes.
- **Clean Wikilink Syntax**: Ensure all references and citations are formatted as active wikilinks (`[[Target Note]]` or `([[sources/<source-slug>]])`). NEVER enclose wikilinks in code backticks (`` `[[...]]` ``).

### 4. Task Archival & Kanban Board Synchronization
- Immediately upon successful authoring and verification of the deliverable:
  1. Update the source task file in `_input/tasks/<task-file>.md`:
     - Update YAML frontmatter: `status: "done"` and `updated: YYYY-MM-DD`.
  2. Move the source task file from the active inbox to the archive:
     ```bash
     mv "_input/tasks/<task-file>.md" "_input/tasks/archived/<task-file>.md"
     ```
  3. Move the task card in `_input/projects/infra/infrastructure_board.md` into `## ✅ Done`:
     - Move `- [ ] [[_input/tasks/<task-file>|...]]` to `- [x] [[_input/tasks/archived/<task-file>|...]]` under `## ✅ Done`.
  4. Verify that `_input/tasks/` remains clean for open tasks while historical instructions and links remain unbroken on the Kanban board.

### 5. Catalog & Ledger Logging
- Append an audit entry to `wiki/log.md`:
  `## [YYYY-MM-DD] task | <task-title> | Executed task query; generated deliverable in _input/drafts/; updated task status to done and moved card to Done on infrastructure board.`
