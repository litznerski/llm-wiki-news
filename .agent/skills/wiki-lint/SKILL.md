---
name: wiki-lint
description: Audits the Sudan News & OSINT Obsidian vault for broken links, orphan notes, taxonomy drift, unescaped table pipes, Mermaid errors, and schema compliance.
---

# Wiki Lint Skill (`wiki-lint`)

## Execution Sequence
1. Check graph index synchronization:
   `ki status -v -C wiki` (detects drifted, unindexed, or deleted markdown files).
2. Run the vault audit script across all `.md` files in `wiki/` (`wiki/events/`, `wiki/actors/`, `wiki/locations/`, `wiki/themes/`, `wiki/timelines/`, `wiki/sources/`, `wiki/syntheses/`, `wiki/ingestions/`):
   `python3 scripts/lint_vault.py`
3. Parse all bracket patterns `[[...]]`.
4. Detect:
   - Index parity drift between local files and Neo4j / ArcadeDB.
   - Broken link targets.
   - Non-canonical directory prefixes in wikilinks (`[[wiki/events/...]]`, `[[wiki/actors/...]]`, `[[wiki/locations/...]]`, `[[wiki/themes/...]]`).
   - Malformed backticked wikilinks (`` `[[...]]` ``) that render as code spans instead of active links.
   - Mermaid diagram errors (wikilinks `[[...]]` in labels, unquoted special characters `:&()`, unbalanced quotes, invalid headers).
   - Unescaped table pipes in wikilinks (`| [[Target|Alias]] |` -> must be `| [[Target\|Alias]] |`).
   - Table structure errors (row column count mismatches against delimiter rows, especially in Section 5 Claim Comparison Matrices).
   - Files with zero inbound links (orphans).
   - Missing mandatory frontmatter attributes (`title`, `type`, `subtype`, `tags`, `last_updated`, `sources`, `reliability_score`, plus `admiralty_rating` on events/sources and `pcode` on locations/events).
5. Output results as a Markdown diagnostic table with suggested remediations.
