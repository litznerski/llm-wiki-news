---
name: wiki-task
description: Executes task specifications from raw/tasks/, resolves context against the knowledge graph, drafts deliverables into raw/drafts/, updates task frontmatter to status done, and moves the task card to Done on the Kanban board.
---

# Wiki Task Skill (`wiki-task`)

## Objective
Execute task specifications and query briefs placed into `raw/tasks/`, ground deliverables in the compiled knowledge graph (`wiki/`), author structured outputs into `raw/drafts/` (or target project directories), update the task file's frontmatter to `status: done`, and **move the task card to the `Done` column** on the Kanban board (`raw/projects/infra/infrastructure_board.md`), preserving the task file and its instructions in `raw/tasks/`.

---

## Execution Sequence

### 1. Task Ingestion & Verification
- Confirm the target task file exists in `raw/tasks/`.
- Read and extract:
  - User directives and target deliverables.
  - Background context and constraints.
  - Specific questions, comparative frameworks, or audiences.
- Update the task card on `raw/projects/infra/infrastructure_board.md` to `## ⚡ In Progress` (if not already there).

### 2. Context Resolution & Vault Grounding via `ki`
- Cross-reference keywords and explicit `[[wikilinks]]` using `ki search "<term>"`, `ki outline`, and `wiki/index.md`.
- Retrieve targeted content slices using `ki get --type full "<uri>"` (or `--type content`) instead of dumping full files into context.
- Ensure deliverables maintain strict epistemic consistency with existing theories, findings, and brand positioning (e.g., `[[Knowledge Lab]]`, `[[Productive Cognitive Friction]]`).

### 3. Deliverable Production
- Author the deliverable in `raw/drafts/<deliverable-title>.md` (or the destination specified in the task brief).
- Ensure mandatory frontmatter is included:
  ```yaml
  ---
  title: "Deliverable Title"
  task_origin: "[[raw/tasks/<task-slug>.md]]"
  sources: ["[[sources/source-slug]]", "[[concepts/concept-slug]]"]
  date: YYYY-MM-DD
  ---
  ```
- Structure the content using Obsidian-native primitives (GFM tables, Mermaid diagrams, and Obsidian callouts per `wiki-format`). Never use raw ASCII art boxes.
- **Clean Wikilink Syntax**: Ensure all references and citations are formatted as active wikilinks (`[[Target Note]]` or `([[sources/<source-slug>]])`). NEVER enclose wikilinks in code backticks (`` `[[...]]` ``).

### 4. Task Archival & Kanban Board Synchronization
- Immediately upon successful authoring and verification of the deliverable:
  1. Update the source task file in `raw/tasks/<task-file>.md`:
     - Update YAML frontmatter: `status: "done"` and `updated: YYYY-MM-DD`.
  2. Move the source task file from the active inbox to the archive:
     ```bash
     mv "raw/tasks/<task-file>.md" "raw/tasks/archived/<task-file>.md"
     ```
  3. Move the task card in `raw/projects/infra/infrastructure_board.md` into `## ✅ Done`:
     - Move `- [ ] [[raw/tasks/<task-file>|...]]` to `- [x] [[raw/tasks/archived/<task-file>|...]]` under `## ✅ Done`.
  4. Verify that `raw/tasks/` remains clean for open tasks while historical instructions and links remain unbroken on the Kanban board.

### 5. Catalog & Ledger Logging
- Append an audit entry to `wiki/log.md`:
  `## [YYYY-MM-DD] task | <task-title> | Executed task query; generated deliverable; updated task status to done and moved card to Done on infrastructure board.`
