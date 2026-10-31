#!/usr/bin/env python3
"""
scripts/lint_vault.py
Audits the Obsidian vault for broken links, orphan notes, and schema compliance.
Part of Andrej Karpathy's LLM Wiki implementation.
"""

import os
import re
import sys
import argparse
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"
REQUIRED_FRONTMATTER_FIELDS = ["title", "type", "tags", "last_updated", "sources", "reliability_score"]
EXEMPT_FILES = {"index.md", "overview.md", "log.md", "glossary.md"}

def parse_frontmatter(content):
    """Extract frontmatter dict if present."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    fm_text = parts[1]
    data = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
    return data

def get_all_wiki_files():
    """Return dictionary of stem -> Path and relative path -> Path."""
    files_by_stem = {}
    files_by_rel = {}
    for root, _, files in os.walk(WIKI_DIR):
        for f in files:
            if f.endswith(".md"):
                p = Path(root) / f
                rel = p.relative_to(VAULT_ROOT)
                files_by_stem[p.stem] = p
                files_by_rel[str(rel)] = p
                # also register without extension
                files_by_rel[str(rel.with_suffix(""))] = p
    return files_by_stem, files_by_rel

def extract_links(content):
    """Extract wikilinks from content [[Target|Alias]] -> Target, ignoring code blocks and backticks."""
    # Strip fenced code blocks
    content_no_code = re.sub(r"```[\s\S]*?```", "", content)
    # Strip inline code spans
    content_no_code = re.sub(r"`[^`]*`", "", content_no_code)
    
    raw_links = re.findall(r"\[\[(.*?)\]\]", content_no_code)
    cleaned = []
    for link in raw_links:
        target = re.split(r"\\?\|", link)[0].split("#")[0].strip()
        if target:
            cleaned.append(target)
    return cleaned

def lint(check_cot: bool = False):
    files_by_stem, files_by_rel = get_all_wiki_files()
    inbound_links = {p: 0 for p in files_by_stem.values()}
    issues = []

    all_notes = []
    for root, _, files in os.walk(WIKI_DIR):
        for f in files:
            if f.endswith(".md"):
                all_notes.append(Path(root) / f)

    for p in all_notes:
        content = p.read_text(encoding="utf-8")
        rel_path = p.relative_to(VAULT_ROOT)

        # 1. Frontmatter check (only for compiled notes, not index/overview/log/glossary)
        if p.name not in EXEMPT_FILES:
            fm = parse_frontmatter(content)
            if fm is None:
                issues.append({
                    "type": "Schema Missing",
                    "file": str(rel_path),
                    "desc": "Missing YAML frontmatter",
                    "action": "Add required frontmatter header"
                })
            else:
                missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
                if missing:
                    issues.append({
                        "type": "Schema Incomplete",
                        "file": str(rel_path),
                        "desc": f"Missing attributes: {', '.join(missing)}",
                        "action": f"Add {missing} to frontmatter"
                    })

        # 2. Check for malformed backticked wikilinks outside fenced code blocks
        content_no_fences = re.sub(r"```[\s\S]*?```", "", content)
        backticked_links = re.findall(r"`(\[\[[^`\r\n]+?\]\])`", content_no_fences)
        if backticked_links:
            issues.append({
                "type": "Malformed Link",
                "file": str(rel_path),
                "desc": f"Found {len(backticked_links)} backticked wikilink(s), e.g. `{backticked_links[0]}`",
                "action": "Strip backticks so links become native [[wikilinks]]"
            })

        # 3. Check Mermaid diagram syntax & Clean Label Invariant
        mermaid_blocks = re.finditer(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
        for m_match in mermaid_blocks:
            m_text = m_match.group(1)
            preceding_text = content[:m_match.start()]
            block_start_line = preceding_text.count("\n") + 1

            m_lines = m_text.splitlines()
            first_non_empty = next((l.strip() for l in m_lines if l.strip()), "")
            valid_headers = ("flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2", "classDiagram", "erDiagram", "xychart-beta", "pie", "gitGraph", "journey")
            if not any(first_non_empty.startswith(vh) for vh in valid_headers):
                issues.append({
                    "type": "Mermaid Header Error",
                    "file": f"{rel_path}:{block_start_line}",
                    "desc": f"Mermaid block missing valid diagram header: '{first_non_empty[:30]}'",
                    "action": "Add valid diagram header (e.g. `flowchart TD`)"
                })

            for l_idx, l_str in enumerate(m_lines, 1):
                curr_lno = block_start_line + l_idx
                s = l_str.strip()
                if not s or s.startswith("%%"):
                    continue

                # A. Wikilinks inside mermaid [[...]]
                if "[[" in s and "]]" in s:
                    issues.append({
                        "type": "Mermaid Wikilink Error",
                        "file": f"{rel_path}:{curr_lno}",
                        "desc": f"Wikilink [[...]] inside Mermaid diagram breaks parsing and SVG rendering: `{s}`",
                        "action": 'Remove [[...]] brackets and use plain text label enclosed in quotes (e.g. `id["Label"]`)'
                    })

                # B. Unquoted special characters in square brackets
                unquoted_spec = re.search(r'([A-Za-z0-9_]+)\[([^"\n\[\]]*?[:&()][^"\n\[\]]*?)\]', s)
                if unquoted_spec:
                    issues.append({
                        "type": "Mermaid Syntax Error",
                        "file": f"{rel_path}:{curr_lno}",
                        "desc": f"Unquoted special character in Mermaid node label: `{unquoted_spec.group(0)}`",
                        "action": f'Enclose label in double quotes: `{unquoted_spec.group(1)}["..."]`'
                    })

                # C. Odd number of quotes
                clean_q = s.replace(r'\"', '')
                if clean_q.count('"') % 2 != 0:
                    issues.append({
                        "type": "Mermaid Quote Mismatch",
                        "file": f"{rel_path}:{curr_lno}",
                        "desc": f"Unbalanced quotes in Mermaid line: `{s}`",
                        "action": "Ensure all node labels have balanced double quotes"
                    })

        # 4. Check for unescaped pipes in table wikilinks and table structure integrity
        lines = content.splitlines()
        in_code = False
        current_table = []
        delim_pattern = re.compile(r"^:?-+:?$")
        pipe_pattern = re.compile(r"\[\[([^\]\r\n]*?(?<!\\)\|[^\]\r\n]*?)\]\]")

        def evaluate_table(table_rows):
            tbl_issues = []
            if not table_rows:
                return tbl_issues
            # A. Check for unescaped pipes inside table wikilinks
            for lno, ltext in table_rows:
                matches = pipe_pattern.findall(ltext)
                if matches:
                    tbl_issues.append({
                        "type": "Table Pipe Error",
                        "file": f"{rel_path}:{lno}",
                        "desc": f"Unescaped pipe inside table wikilink: `[[{matches[0]}]]`",
                        "action": "Escape pipe as \\| (e.g. [[Target\\|Alias]]) or use unaliased link"
                    })
            # B. Check column count consistency against delimiter row
            delim_idx = -1
            delim_cols = 0
            for idx, (lno, ltext) in enumerate(table_rows):
                s = ltext.strip()
                inner = s[1:-1]
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", inner)]
                if len(cells) > 0 and all(delim_pattern.match(c) for c in cells):
                    delim_idx = idx
                    delim_cols = len(cells)
                    break
            if delim_idx != -1 and delim_cols > 0:
                for lno, ltext in table_rows:
                    s = ltext.strip()
                    inner = s[1:-1]
                    cells = [c.strip() for c in re.split(r"(?<!\\)\|", inner)]
                    if len(cells) != delim_cols:
                        tbl_issues.append({
                            "type": "Table Column Mismatch",
                            "file": f"{rel_path}:{lno}",
                            "desc": f"Row has {len(cells)} column(s), expected {delim_cols} from delimiter",
                            "action": "Verify cell delimiters and check for unescaped pipes"
                        })
            return tbl_issues

        for line_no, line in enumerate(lines, 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                if current_table:
                    issues.extend(evaluate_table(current_table))
                    current_table = []
                continue
            if in_code:
                continue
            if line.strip().startswith("|") and line.strip().endswith("|"):
                current_table.append((line_no, line))
            else:
                if current_table:
                    issues.extend(evaluate_table(current_table))
                    current_table = []
        if current_table:
            issues.extend(evaluate_table(current_table))

        # 5. Extract links and verify targets
        links = extract_links(content)
        for link in links:
            # Check if link resolves by relative path or stem
            target_file = None
            if link in files_by_rel:
                target_file = files_by_rel[link]
            elif f"{link}.md" in files_by_rel:
                target_file = files_by_rel[f"{link}.md"]
            elif f"wiki/{link}" in files_by_rel:
                target_file = files_by_rel[f"wiki/{link}"]
            elif f"wiki/{link}.md" in files_by_rel:
                target_file = files_by_rel[f"wiki/{link}.md"]
            elif link in files_by_stem:
                target_file = files_by_stem[link]
            elif link.split("/")[-1] in files_by_stem:
                target_file = files_by_stem[link.split("/")[-1]]
            elif Path(link).stem in files_by_stem:
                target_file = files_by_stem[Path(link).stem]
            elif (VAULT_ROOT / link).exists():
                target_file = VAULT_ROOT / link
            elif (VAULT_ROOT / f"{link}.md").exists():
                target_file = VAULT_ROOT / f"{link}.md"

            if target_file:
                inbound_links[target_file] = inbound_links.get(target_file, 0) + 1
            else:
                # Target doesn't exist
                issues.append({
                    "type": "Dead Link",
                    "file": str(rel_path),
                    "desc": f"Links to non-existent [[{link}]]",
                    "action": f"Create [[{link}]] or fix link"
                })

        # 6. Generation 3 Dual-Flow CoT Concept Structure Audit (optional via --cot)
        if check_cot and "concepts/" in str(rel_path):
            if not re.search(r">\s*\[!IMPORTANT\]\s*Definitional Anchor", content, re.IGNORECASE):
                issues.append({
                    "type": "CoT Lead Callout Missing",
                    "file": str(rel_path),
                    "desc": "Lead section missing '> [!IMPORTANT] Definitional Anchor' callout",
                    "action": "Wrap lead definition in '> [!IMPORTANT] Definitional Anchor' callout"
                })

            canonical_stages = [
                (1, r"##\s*1[\.\:]\s*Core Thesis", "1. Core Thesis"),
                (2, r"##\s*2[\.\:]\s*(Causal Anatomy|Underlying Mechanics)", "2. Causal Anatomy & Underlying Mechanics"),
                (3, r"##\s*3[\.\:]\s*(Manifestations|Failure Modes|Pathologies)", "3. Manifestations & Failure Modes"),
                (4, r"##\s*4[\.\:]\s*(Prescriptive Mitigations|Counter-Architectures)", "4. Prescriptive Mitigations & Counter-Architectures"),
                (5, r"##\s*5[\.\:]\s*(Empirical Boundaries|Contradictions)", "5. Empirical Boundaries & Contradictions"),
                (6, r"##\s*6[\.\:]\s*(Related Primitives|Synthesis Catalog|Related Notes)", "6. Related Primitives & Synthesis Catalog")
            ]
            missing_stages = []
            for num, pat, title in canonical_stages:
                if not re.search(pat, content, re.IGNORECASE):
                    missing_stages.append(f"Stage {num} ({title})")
            
            if missing_stages:
                issues.append({
                    "type": "CoT Structure Gap",
                    "file": str(rel_path),
                    "desc": f"Missing canonical CoT stage(s): {', '.join(missing_stages)}",
                    "action": "Refactor to Generation 3 Dual-Flow CoT 6-stage epistemic arc"
                })

    # 7. Orphan detection
    for p, in_count in inbound_links.items():
        if p.name in EXEMPT_FILES:
            continue
        if in_count == 0:
            issues.append({
                "type": "Orphan Node",
                "file": str(p.relative_to(VAULT_ROOT)),
                "desc": "No inbound [[wikilinks]] from any note",
                "action": "Link from wiki/index.md or related concept"
            })

    # Render Markdown Report
    print("# Knowledge Base Diagnostic Report\n")
    if not issues:
        print("All checks passed! Vault graph integrity is 100% compliant.")
        return 0

    print(f"Found {len(issues)} issue(s):\n")
    print("| Issue Type | File Location | Problem Description | Recommended Action |")
    print("| :--- | :--- | :--- | :--- |")
    for iss in issues:
        print(f"| **{iss['type']}** | `{iss['file']}` | {iss['desc']} | {iss['action']} |")
    print("")
    return 1

def main():
    parser = argparse.ArgumentParser(description="Audit Obsidian vault for broken links, orphan notes, and schema compliance.")
    parser.add_argument("--cot", action="store_true", help="Audit wiki/concepts/ notes for Generation 3 Dual-Flow CoT 6-stage epistemic arcs")
    args = parser.parse_args()
    return lint(check_cot=args.cot)

if __name__ == "__main__":
    sys.exit(main())
