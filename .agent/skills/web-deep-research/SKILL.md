---
name: web-deep-research
description: Conducts multi-angle deep web research on a specific topic, theory, or entity and compiles a structured research dossier into raw/research/. Use whenever the user asks to research, explore the web, or investigate literature for a topic.
---

# Web Deep Research Skill

## Objective
Execute thorough, multi-perspective web research on a specified domain concept, academic debate, entity, or technology, and compile the synthesized findings into a permanent primary evidence dossier saved directly to `raw/research/<slug>.md`.

---

## Execution Sequence

### 1. Scope Formulation & Query Decomposition
Break the topic into at least 3 distinct inquiry angles:
- **Theoretical Foundations**: Originators, canonical definitions, and mechanisms.
- **Empirical Evidence**: Studies, statistics, benchmark data, and real-world observations.
- **Tensions & Counter-Perspectives**: Critical critiques, edge cases, and active debates.
- **Institutional / Policy Context**: University, governmental, or industry standards.

### 2. Multi-Step Web Exploration
- Formulate targeted search queries covering each angle.
- Inspect authoritative sources (academic preprints, university press releases, industry analyses, policy frameworks).
- If relevant literature is multilingual (e.g., German / DACH higher education), query in both German and English.

### 3. Vault Contextual Alignment
- Inspect `wiki/index.md` and `wiki/glossary.md` to identify existing related concept or entity notes.
- Ensure new research directly complements or challenges existing notes in the knowledge graph.

### 4. Dossier Construction & Formatting
Compile findings into a Markdown document adhering to this structure:
```markdown
# [Title: Canonical Topic & Subtitle]

- **Research Subject**: Concept deep-dive for [[Target Note]]
- **Target File**: `raw/research/<topic-slug>.md`
- **Date**: YYYY-MM-DD
- **Keywords**: [Comma-separated search keywords]

---

## 1. Executive Summary
[High-level overview of the topic, its significance, and core dilemma]

## 2. Theoretical & Conceptual Frameworks
[Foundations, mechanisms, key definitions, and academic lineage]

## 3. Empirical Findings & Real-World Observations
[Concrete data, field reports, and study outcomes]

## 4. Institutional, Policy, or Market Dynamics
[Standards, organizational frameworks, and implementation challenges]

## 5. Connections to Vault Architecture ([[Knowledge Lab]])
[Explicit mapping to existing vault concepts, Socratic models, or learning frameworks]

## 6. Primary References & Literature Grounding
[Numbered list of literature, author attributions, and URLs]
```

### 5. File Persistence & Verification
1. Verify `raw/research/` directory exists (`mkdir -p raw/research`).
2. Write the compiled dossier to `raw/research/<topic-slug>.md`.
3. If the research was initiated from an active brief in `raw/tasks/<task-slug>.md`, automatically move that file to the archive:
   ```bash
   mv "raw/tasks/<task-slug>.md" "raw/tasks/archived/<task-slug>.md"
   ```
4. Inform the user and suggest immediate compilation via:
   `/ingest raw/research/<topic-slug>.md`

