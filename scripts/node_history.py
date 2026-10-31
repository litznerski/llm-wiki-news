#!/usr/bin/env python3
"""
scripts/node_history.py
Query and visualize the epistemic evolution of any concept or entity across wiki/ingestions/ dossiers.
Part of the Knowledge Lab Knowledge Base.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

VAULT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"
INGESTIONS_DIR = WIKI_DIR / "ingestions"

# ANSI Color codes
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


def clean_link_text(raw_text: str) -> str:
    """Normalize [[wiki/concepts/Foo|Foo]] or [[Foo]] to 'Foo'."""
    text = raw_text.strip()
    # Remove enclosing wikilink brackets if present
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].strip()
    # If alias exists (target|alias or target\|alias), take alias or clean target
    parts = re.split(r"\\?\|", text)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip()
    target = parts[0].strip()
    # Strip directory prefixes like wiki/concepts/, concepts/, etc.
    if "/" in target:
        target = target.split("/")[-1].strip()
    if target.endswith(".md"):
        target = target[:-3]
    return target


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter using standard library."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm_text = parts[1]
    data: Dict[str, Any] = {}
    current_list_key = None

    for line in fm_text.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue

        # Check for list item under active key
        if line.startswith("  - ") or line.startswith("    - ") or line.startswith("- "):
            item = re.sub(r"^[\s\-]+", "", line).strip().strip('"\'')
            if current_list_key:
                data.setdefault(current_list_key, []).append(item)
            continue

        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if val == "":
                current_list_key = key
                data[key] = []
            elif val.startswith("[") and val.endswith("]"):
                current_list_key = None
                items = [x.strip().strip('"\'') for x in val[1:-1].split(",") if x.strip()]
                data[key] = items
            else:
                current_list_key = None
                data[key] = val.strip('"\'')

    return data


def parse_markdown_tables(content: str) -> Dict[str, List[Dict[str, str]]]:
    """Extract rows from Section 3 (Compiled Nodes) and Section 4 (Refactored Nodes)."""
    # Replace escaped pipes inside brackets or cells to simplify column splitting
    # Replace \| with a placeholder
    safe_content = content.replace(r"\|", "—ESCAPEDPIPE—")

    section_3_rows = []
    section_4_rows = []

    # Section 3: Compiled Knowledge Nodes
    s3_match = re.search(r"## 3\.\s*Compiled Knowledge Nodes[\s\S]*?(?=##|\Z)", safe_content)
    if s3_match:
        for line in s3_match.group(0).splitlines():
            line = line.strip()
            if line.startswith("|") and not re.match(r"^\|\s*:?---", line) and not "Node Title" in line:
                cols = [c.replace("—ESCAPEDPIPE—", "|").strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 3:
                    section_3_rows.append({
                        "type": cols[0],
                        "node": clean_link_text(cols[1]),
                        "raw_node": cols[1],
                        "summary": cols[2]
                    })

    # Section 4: Refactored Nodes & Epistemic Evolution
    s4_match = re.search(r"## 4\.\s*Refactored Nodes & Epistemic Evolution[\s\S]*?(?=##|\Z)", safe_content)
    if s4_match:
        for line in s4_match.group(0).splitlines():
            line = line.strip()
            if line.startswith("|") and not re.match(r"^\|\s*:?---", line) and not "Refactored Node" in line:
                cols = [c.replace("—ESCAPEDPIPE—", "|").strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 3:
                    section_4_rows.append({
                        "node": clean_link_text(cols[0]),
                        "raw_node": cols[0],
                        "section": cols[1],
                        "update": cols[2]
                    })

    return {"compiled": section_3_rows, "refactored": section_4_rows}


def scan_dossiers() -> List[Dict[str, Any]]:
    """Scan and parse all dossiers in wiki/ingestions/."""
    dossiers = []
    if not INGESTIONS_DIR.exists():
        return dossiers

    for root, _, files in os.walk(INGESTIONS_DIR):
        for f in files:
            if f.endswith(".md"):
                file_path = Path(root) / f
                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception:
                    continue

                fm = parse_frontmatter(content)
                tables = parse_markdown_tables(content)

                # Determine date: frontmatter > folder name > stat
                date = fm.get("last_updated") or fm.get("date")
                if not date:
                    # check if parent folder is YYYY-MM-DD
                    parent_name = file_path.parent.name
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", parent_name):
                        date = parent_name
                    else:
                        date = "Unknown"

                rel_path = file_path.relative_to(VAULT_ROOT)

                # Collect cleaned concept/entity/refactor lists
                concepts_created = [clean_link_text(x) for x in fm.get("concepts_created", [])]
                entities_created = [clean_link_text(x) for x in fm.get("entities_created", [])]
                nodes_refactored = [clean_link_text(x) for x in fm.get("nodes_refactored", [])]
                sources = [clean_link_text(x) for x in fm.get("sources", [])]

                dossiers.append({
                    "path": str(rel_path),
                    "slug": file_path.stem,
                    "date": str(date),
                    "frontmatter": fm,
                    "concepts_created": concepts_created,
                    "entities_created": entities_created,
                    "nodes_refactored": nodes_refactored,
                    "sources": sources,
                    "tables": tables
                })

    # Sort dossiers chronologically
    dossiers.sort(key=lambda x: (x["date"], x["slug"]))
    return dossiers


def match_node(query: str, target: str, exact: bool = False) -> bool:
    """Compare query with target name."""
    if exact:
        return query.lower() == target.lower()
    return query.lower() in target.lower()


def find_node_history(query: str, dossiers: List[Dict[str, Any]], exact: bool = False) -> List[Dict[str, Any]]:
    """Collect all touchpoints for a given node query across dossiers."""
    history = []

    for d in dossiers:
        matched_as = None
        exact_title = None

        # Check concepts created
        for c in d["concepts_created"]:
            if match_node(query, c, exact):
                matched_as = "CREATED_CONCEPT"
                exact_title = c
                break

        # Check entities created
        if not matched_as:
            for e in d["entities_created"]:
                if match_node(query, e, exact):
                    matched_as = "CREATED_ENTITY"
                    exact_title = e
                    break

        # Check refactored nodes
        if not matched_as:
            for r in d["nodes_refactored"]:
                if match_node(query, r, exact):
                    matched_as = "REFACTORED"
                    exact_title = r
                    break

        # Check tables fallback
        if not matched_as:
            for row in d["tables"]["compiled"]:
                if match_node(query, row["node"], exact):
                    matched_as = "CREATED_CONCEPT" if "concept" in row["type"].lower() else "CREATED_ENTITY"
                    exact_title = row["node"]
                    break

        if not matched_as:
            for row in d["tables"]["refactored"]:
                if match_node(query, row["node"], exact):
                    matched_as = "REFACTORED"
                    exact_title = row["node"]
                    break

        if matched_as:
            # Extract specific table row details
            section_modified = "Initial Creation" if "CREATED" in matched_as else "General"
            update_detail = "Initial conceptual/entity compilation." if "CREATED" in matched_as else "Refactored node."

            if "CREATED" in matched_as:
                for row in d["tables"]["compiled"]:
                    if match_node(query, row["node"], exact):
                        update_detail = row["summary"]
                        break
            else:
                for row in d["tables"]["refactored"]:
                    if match_node(query, row["node"], exact):
                        section_modified = row["section"]
                        update_detail = row["update"]
                        break

            history.append({
                "date": d["date"],
                "event": matched_as,
                "node_name": exact_title or query,
                "dossier_path": d["path"],
                "dossier_slug": d["slug"],
                "sources": d["sources"],
                "section": section_modified,
                "detail": update_detail
            })

    return history


def list_all_nodes(dossiers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate all unique nodes across dossiers."""
    nodes: Dict[str, Dict[str, Any]] = {}

    for d in dossiers:
        date = d["date"]
        for c in d["concepts_created"]:
            if c:
                item = nodes.setdefault(c, {"type": "Concept", "created": date, "touchpoints": 0, "dossiers": []})
                item["touchpoints"] += 1
                item["dossiers"].append(d["slug"])

        for e in d["entities_created"]:
            if e:
                item = nodes.setdefault(e, {"type": "Entity", "created": date, "touchpoints": 0, "dossiers": []})
                item["touchpoints"] += 1
                item["dossiers"].append(d["slug"])

        for r in d["nodes_refactored"]:
            if r:
                item = nodes.setdefault(r, {"type": "Concept/Entity", "created": None, "touchpoints": 0, "dossiers": []})
                item["touchpoints"] += 1
                item["dossiers"].append(d["slug"])

    return nodes


def render_pretty(query: str, history: List[Dict[str, Any]], use_color: bool = True):
    """Render terminal colored timeline."""
    c_bold = BOLD if use_color else ""
    c_dim = DIM if use_color else ""
    c_cyan = CYAN if use_color else ""
    c_green = GREEN if use_color else ""
    c_yellow = YELLOW if use_color else ""
    c_magenta = MAGENTA if use_color else ""
    c_reset = RESET if use_color else ""

    node_title = history[0]["node_name"] if history else query

    print()
    print(f"{c_bold}{c_cyan}{'═' * 80}{c_reset}")
    print(f"{c_bold}EPISTEMIC EVOLUTION DATABASE: [[{node_title}]]{c_reset}")
    print(f"{c_dim}Chronological trace across wiki/ingestions/ dossiers{c_reset}")
    print(f"{c_cyan}{'═' * 80}{c_reset}")

    if not history:
        print(f"\n{c_yellow}No historical ingestion records found matching '{query}'.{c_reset}\n")
        print(f"Tip: Run with --list to view all tracked concepts and entities.")
        return

    for i, h in enumerate(history, 1):
        if h["event"] == "CREATED_CONCEPT":
            badge = f"{c_green}🌱 CREATED (Concept){c_reset}"
        elif h["event"] == "CREATED_ENTITY":
            badge = f"{c_green}🌱 CREATED (Entity){c_reset}"
        else:
            badge = f"{c_yellow}🔄 REFACTORED{c_reset}"

        src_text = f"from [[{h['sources'][0]}]]" if h["sources"] else ""

        print(f"\n[{h['date']}] {badge} {c_dim}{src_text}{c_reset}")
        print(f"  {c_bold}Dossier:{c_reset} {h['dossier_path']}")
        if h["section"] and h["section"] != "General":
            print(f"  {c_bold}Section Modified:{c_reset} {c_magenta}{h['section']}{c_reset}")
        print(f"  {c_bold}Epistemic Evolution:{c_reset} {h['detail']}")
        if i < len(history):
            print(f"{c_dim}{'─' * 80}{c_reset}")

    print(f"\n{c_cyan}{'═' * 80}{c_reset}")
    creations = sum(1 for h in history if "CREATED" in h["event"])
    refactors = sum(1 for h in history if h["event"] == "REFACTORED")
    print(f"{c_bold}Summary:{c_reset} {len(history)} total touchpoints ({creations} creations, {refactors} refactors) across {len(set(h['date'] for h in history))} dates.")
    print(f"{c_cyan}{'═' * 80}{c_reset}\n")


def render_markdown(query: str, history: List[Dict[str, Any]]):
    """Render markdown table format."""
    node_title = history[0]["node_name"] if history else query
    print(f"### 📜 Epistemic Evolution Timeline: [[{node_title}]]\n")
    print(f"| Date | Event | Ingestion Dossier | Section(s) Modified | Epistemic Updates & Theoretical Mechanism |")
    print(f"| :--- | :--- | :--- | :--- | :--- |")
    for h in history:
        event = "🌱 Created" if "CREATED" in h["event"] else "🔄 Refactored"
        dossier_link = f"[[{h['dossier_path']}|{h['dossier_slug']}]]"
        section = h["section"]
        detail = h["detail"].replace("|", "\\|").replace("\n", " ")
        print(f"| {h['date']} | {event} | {dossier_link} | {section} | {detail} |")
    print()


def render_compact(history: List[Dict[str, Any]]):
    """Render 1 line per event."""
    for h in history:
        event = "CREATED" if "CREATED" in h["event"] else "REFACTORED"
        print(f"{h['date']} | {event:<10} | {h['dossier_slug']:<60} | {h['section']}")


def main():
    parser = argparse.ArgumentParser(description="Query node epistemic evolution across wiki/ingestions/ dossiers.")
    parser.add_argument("node", nargs="?", help="Concept or entity name to search (e.g., 'Cognitive Surrender')")
    parser.add_argument("--format", "-f", choices=["pretty", "markdown", "json", "compact"], default="pretty", help="Output format")
    parser.add_argument("--list", "-l", action="store_true", help="List all tracked concepts and entities with touchpoint counts")
    parser.add_argument("--exact", "-e", action="store_true", help="Match exact node title")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()

    dossiers = scan_dossiers()
    if not dossiers:
        print(f"No dossiers found in {INGESTIONS_DIR}.", file=sys.stderr)
        sys.exit(1)

    if args.list:
        nodes = list_all_nodes(dossiers)
        print(f"\nTracked Knowledge Nodes across {len(dossiers)} Ingestion Dossiers:\n")
        print(f"{'Node Title':<55} | {'Type':<12} | {'Created':<10} | {'Touchpoints'}")
        print(f"{'-' * 55}-|-{'-' * 12}-|-{'-' * 10}-|------------")
        sorted_nodes = sorted(nodes.items(), key=lambda x: (-x[1]["touchpoints"], x[0].lower()))
        for name, meta in sorted_nodes:
            created_str = meta["created"] or "Historical"
            print(f"{name:<55} | {meta['type']:<12} | {created_str:<10} | {meta['touchpoints']}")
        print(f"\nTotal unique nodes: {len(nodes)}\n")
        return

    query = args.node
    if not query:
        try:
            query = input("Enter concept or entity to search (or 'list' to view all): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
        if not query:
            return
        if query.lower() == "list":
            args.list = True
            main()
            return

    history = find_node_history(query, dossiers, exact=args.exact)

    use_color = sys.stdout.isatty() and not args.no_color

    if args.format == "json":
        print(json.dumps(history, indent=2))
    elif args.format == "markdown":
        render_markdown(query, history)
    elif args.format == "compact":
        render_compact(history)
    else:
        render_pretty(query, history, use_color=use_color)


if __name__ == "__main__":
    main()
