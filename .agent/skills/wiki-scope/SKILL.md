---
name: wiki-scope
description: Scans a source document before ingestion, cross-references existing vault catalogs, filters by pedagogical significance, and generates a Scoped Ingestion Manifest with dynamic concept/entity quotas.
---

# Wiki Scope Skill (`wiki-scope`)

## Objective
Act as the mandatory epistemic reconnaissance and planning phase prior to compiling any primary document into the `wiki/` knowledge graph. 

Instead of imposing static or arbitrary extraction limits, `wiki-scope` analyzes the incoming document against the current state of the knowledge graph (`wiki/index.md` and `wiki/glossary.md`), separates candidate concepts from entities, filters out trivial noise, and outputs a **Scoped Ingestion Manifest** that defines the dynamic compilation quota.

---

## Execution Sequence

### 1. Document & Vault Cross-Referencing
1. Read the target document in `raw/` using standard viewer.
2. Read `wiki/index.md` and `wiki/glossary.md` to map existing vault topography.
3. Extract candidate primitives into three distinct pools:
   - **Candidate Concepts**: Abstract frameworks, cognitive mechanics, pedagogical models, or empirical phenomena.
   - **Candidate Entities**: Concrete researchers, historical figures, organizations, software platforms, or neural models.
   - **Existing Nodes to Refactor**: Notes already present in `wiki/concepts/` or `wiki/entities/` where the new source introduces new evidence, modern extensions, or empirical contradictions.

### 2. Pedagogical Significance Filtering
Filter candidate concepts and entities using three qualitative criteria (must score $\ge 0.70$ on composite significance):
- **Mechanistic Depth**: Does the concept possess internal causal mechanisms, structured steps, or theoretical foundations? (Reject descriptive buzzwords and trivial generic nouns like "video lecture", "email", or "dashboard").
- **Network Interconnectivity**: Can this node plausibly connect to at least $\ge 2$ existing nodes or themes in `wiki/overview.md`?
- **Domain Relevance**: Does the item directly advance `Knowledge Lab`'s core research axes:
  - Cognitive friction, Socratic AI, and learning architecture.
  - Generative AI governance, ISD models, and cognitive debt.
  - Personal knowledge management and compounding intelligence.
  - Digital marketing architecture and unit economics.

### 3. Generate the Scoped Ingestion Manifest
Output the manifest in standard Markdown format (which is presented to the user during scoping and subsequently archived into Section 2 of `wiki/ingestions/YYYY-MM-DD/<source-slug>.md`):

```markdown
### 📋 Scoped Ingestion Manifest: `<source-slug>`
- **Source Complexity**: [Compact / Moderate / Deep Research / Monograph]
- **Target Dynamic Quota**: **N New Concepts** | **M New Entities** | **K Refactors**

#### 1. Candidate Concepts (N)
- `[[Concept Name]]`: Brief 1-line justification of mechanism & significance.

#### 2. Candidate Entities (M)
- `[[Entity Name]]`: Role, affiliation, or key contribution.

#### 3. Nodes to Refactor (K)
- `[[Existing Note]]`: Specific update (e.g., add contradiction, update empirical stats, or add sub-framework).

#### 4. Workload Execution Strategy
- [Single-thread sequential (Total nodes ≤ 6) | Map-Reduce parallel subagents (Total nodes > 6)]
```

### 4. Setting the Dynamic Quota & Interaction Gate
- The manifest's counts ($N$ concepts + $M$ entities) become the strict, explicit compilation target for `wiki-ingest`.
- **Fast-Path**: If Total Nodes ($N + M$) $\le 6$, proceed automatically into `wiki-ingest`.
- **Review Gate**: If Total Nodes ($N + M$) $> 6$, present the manifest to the user for confirmation (`"proceed"` or adjustments) before file creation commences.
- **Permanent Archival**: Upon completion of compilation, the manifest and evaluation decisions are permanently stored in the ingestion dossier at `wiki/ingestions/YYYY-MM-DD/<source-slug>.md`.
