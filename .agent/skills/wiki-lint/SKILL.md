---
name: wiki-lint
description: Audits the Obsidian vault for broken links, orphan notes, and taxonomy drift.
---

# Wiki Lint Skill

## Execution Sequence
1. Check graph index synchronization:
   `ki status -v` (detects drifted, unindexed, or deleted markdown files).
2. Run the vault audit script across all `.md` files in `wiki/`:
   `python3 scripts/lint_vault.py`
3. Parse all bracket patterns `[[...]]`.
4. Detect:
   - Index parity drift between local files and Neo4j.
   - Broken link targets.
   - Malformed backticked wikilinks (`` `[[...]]` ``) that render as code spans instead of active links.
   - Mermaid diagram errors (wikilinks `[[...]]` in labels, unquoted special characters `:&()`, unbalanced quotes, invalid headers).
   - Unescaped table pipes in wikilinks (`| [[Target|Alias]] |` -> must be `| [[Target\|Alias]] |`).
   - Table structure errors (row column count mismatches against delimiter rows).
   - Files with zero inbound links (orphans).
   - Missing mandatory frontmatter attributes (`title`, `type`, `tags`, `last_updated`, `sources`, `reliability_score`).
5. Output results as a Markdown diagnostic table with suggested remediations.
