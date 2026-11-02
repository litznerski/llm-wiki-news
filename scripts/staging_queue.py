#!/usr/bin/env python3
"""
scripts/staging_queue.py
Zero-Mutation Ingestion Staging & Telemetry Queue for llm-wiki-news.
Cross-references raw harvested evidence in raw/articles/ against distilled source notes
in wiki/sources/ and audit dossiers in wiki/ingestions/ to deterministically classify
articles into STAGED, DRAFT, APPROVED, or COMPILED states.
"""

import os
import sys
import re
import argparse
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

VAULT_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = VAULT_ROOT / "raw" / "articles"
SOURCES_DIR = VAULT_ROOT / "wiki" / "sources"
INGESTIONS_DIR = VAULT_ROOT / "wiki" / "ingestions"
DASHBOARD_FILE = VAULT_ROOT / "_input" / "projects" / "infra" / "staging_dashboard.md"
IGNORE_FILE = VAULT_ROOT / ".staging_ignore"


def normalize_text(text: str) -> str:
    """Normalizes Unicode text to NFC and strips surrounding whitespace/quotes."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text).strip().strip("'\"")
    return normalized


def extract_frontmatter_dict(content: str) -> Dict[str, Any]:
    """Extracts simple YAML frontmatter key-values without third-party dependencies."""
    data = {}
    if not content.startswith("---"):
        return data

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return data

    fm_text = content[3:end_idx]
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            # Convert booleans
            if val.lower() == "true":
                data[key] = True
            elif val.lower() == "false":
                data[key] = False
            else:
                data[key] = val
    return data


@dataclass
class SourceNoteInfo:
    filepath: Path
    slug: str
    title: str
    status: str
    compiled: bool
    raw_file_rel: str
    raw_file_stem: str
    url: str
    publisher: str


@dataclass
class StagedArticle:
    filepath: Path
    filename: str
    title: str
    url: str
    publisher: str
    language: str
    published_date: str
    retrieved_at: str
    status: str  # STAGED, DRAFT, APPROVED, COMPILED, IGNORED
    source_note: Optional[SourceNoteInfo] = None
    ingestion_dossier: Optional[Path] = None


def load_source_notes(sources_dir: Path) -> List[SourceNoteInfo]:
    """Loads and indexes all source notes from wiki/sources/."""
    sources: List[SourceNoteInfo] = []
    if not sources_dir.exists():
        return sources

    for f in sources_dir.glob("*.md"):
        if f.name.startswith("."):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            fm = extract_frontmatter_dict(content)
            raw_file_raw = normalize_text(str(fm.get("raw_file", "")))
            # Clean [[wikilinks]] if present in raw_file
            raw_file_clean = re.sub(r"^\[\[|\]\]$", "", raw_file_raw).strip()
            raw_stem = Path(raw_file_clean).stem.strip() if raw_file_clean else ""

            sources.append(
                SourceNoteInfo(
                    filepath=f,
                    slug=f.stem,
                    title=normalize_text(str(fm.get("title", f.stem))),
                    status=str(fm.get("status", "draft")).lower(),
                    compiled=bool(fm.get("compiled", False)),
                    raw_file_rel=raw_file_clean,
                    raw_file_stem=raw_stem,
                    url=normalize_text(str(fm.get("url", ""))),
                    publisher=normalize_text(str(fm.get("source_outlet", ""))),
                )
            )
        except Exception:
            pass
    return sources


def load_ignored_identifiers(ignore_file: Path) -> Set[str]:
    """Loads patterns of ignored URLs or filenames."""
    ignored = set()
    if ignore_file.exists():
        try:
            for line in ignore_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    ignored.add(normalize_text(line))
        except Exception:
            pass
    return ignored


def load_ingestion_dossiers(ingestions_dir: Path) -> Dict[str, Path]:
    """Indexes compiled ingestion dossiers by source slug."""
    dossiers = {}
    if not ingestions_dir.exists():
        return dossiers

    for f in ingestions_dir.glob("**/*.md"):
        if f.name.startswith("."):
            continue
        dossiers[f.stem] = f
    return dossiers


def inspect_queue(articles_dir: Path, sources_dir: Path, ingestions_dir: Path) -> List[StagedArticle]:
    """Inspects raw/articles/ and resolves the exact lifecycle state of every article."""
    sources = load_source_notes(sources_dir)
    ignored = load_ignored_identifiers(IGNORE_FILE)
    dossiers = load_ingestion_dossiers(ingestions_dir)

    # Build lookup indices for fast matching
    by_raw_stem: Dict[str, SourceNoteInfo] = {}
    by_raw_clean: Dict[str, SourceNoteInfo] = {}
    by_url: Dict[str, SourceNoteInfo] = {}

    for s in sources:
        if s.raw_file_stem:
            by_raw_stem[s.raw_file_stem] = s
        if s.raw_file_rel:
            by_raw_clean[s.raw_file_rel] = s
        if s.url:
            by_url[s.url] = s

    articles: List[StagedArticle] = []
    if not articles_dir.exists():
        return articles

    raw_files = sorted(
        [f for f in articles_dir.glob("*.md") if not f.name.startswith(".")],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )

    for f in raw_files:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        fm = extract_frontmatter_dict(content)
        title = normalize_text(str(fm.get("title", f.stem)))
        url = normalize_text(str(fm.get("source", fm.get("url", ""))))
        publisher = normalize_text(str(fm.get("publisher", "")))
        lang = normalize_text(str(fm.get("language", "")))
        pub_date = normalize_text(str(fm.get("published_date", fm.get("published_at", fm.get("published", "")))))
        retrieved_at = normalize_text(str(fm.get("retrieved_at", fm.get("created", ""))))

        # Fallback date if missing in frontmatter
        if not pub_date:
            m = re.search(r"\b(202[4-6]-[0-1][0-9]-[0-3][0-9])\b", content[:1500])
            pub_date = m.group(1) if m else datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")

        # Derive publisher from URL domain or title suffix if missing
        if not publisher and url:
            if "dabangasudan.org" in url or "Dabanga" in title:
                publisher = "Radio Dabanga"
            elif "bbc.com" in url or "BBC" in title:
                publisher = "BBC News"
            elif "aljazeera.com" in url or "Al Jazeera" in title:
                publisher = "Al Jazeera"
            elif "dw.com" in url:
                publisher = "Deutsche Welle"
            elif "reuters.com" in url:
                publisher = "Reuters"
            elif "sudantribune.com" in url:
                publisher = "Sudan Tribune"
            elif "3ayin.com" in url:
                publisher = "Ayin Network"
            elif "un.org" in url or "ohchr.org" in url or "UN" in title:
                publisher = "United Nations"
            elif "theguardian.com" in url:
                publisher = "The Guardian"
            else:
                m_dom = re.search(r"https?://(?:www\.)?([^/]+)", url)
                publisher = m_dom.group(1) if m_dom else "Independent / Field"

        # Auto-detect language if missing
        if not lang:
            lang = "ar" if re.search(r"[\u0600-\u06FF]", title + content[:500]) else "en"

        norm_filename = normalize_text(f.name)
        norm_stem = normalize_text(f.stem)
        rel_path = f"raw/articles/{f.name}"

        # Check ignored
        if norm_filename in ignored or norm_stem in ignored or (url and url in ignored):
            articles.append(
                StagedArticle(
                    filepath=f,
                    filename=f.name,
                    title=title,
                    url=url,
                    publisher=publisher,
                    language=lang,
                    published_date=pub_date,
                    retrieved_at=retrieved_at,
                    status="IGNORED",
                )
            )
            continue

        # Match against sources
        matched_source = None
        if norm_stem in by_raw_stem:
            matched_source = by_raw_stem[norm_stem]
        elif rel_path in by_raw_clean:
            matched_source = by_raw_clean[rel_path]
        elif norm_filename in by_raw_clean:
            matched_source = by_raw_clean[norm_filename]
        elif url and url in by_url:
            matched_source = by_url[url]

        # Determine status
        dossier = None
        if matched_source:
            if matched_source.slug in dossiers:
                dossier = dossiers[matched_source.slug]

            if matched_source.compiled or dossier:
                status = "COMPILED"
            elif matched_source.status == "approved":
                status = "APPROVED"
            else:
                status = "DRAFT"
        else:
            status = "STAGED"

        articles.append(
            StagedArticle(
                filepath=f,
                filename=f.name,
                title=title,
                url=url,
                publisher=publisher or (matched_source.publisher if matched_source else "Unknown"),
                language=lang or "ar/en",
                published_date=pub_date[:10],
                retrieved_at=retrieved_at,
                status=status,
                source_note=matched_source,
                ingestion_dossier=dossier,
            )
        )

    return articles


def format_cli_table(articles: List[StagedArticle], max_items: int = 50) -> str:
    """Formats queue articles into a clean console table."""
    if not articles:
        return "No articles in this view."

    headers = ["#", "Status", "Publisher", "Lang", "Date", "Title / Target Note"]
    rows = []
    for idx, a in enumerate(articles[:max_items], 1):
        status_badge = {
            "STAGED": "⏳ STAGED",
            "DRAFT": "📝 DRAFT",
            "APPROVED": "🚀 APPROVED",
            "COMPILED": "✅ COMPILED",
            "IGNORED": "🚫 IGNORED",
        }.get(a.status, a.status)

        title_display = a.title[:55] + ("..." if len(a.title) > 55 else "")
        rows.append([str(idx), status_badge, a.publisher[:18], a.language[:5], a.published_date[:10], title_display])

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    line_sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_str = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"

    res = [line_sep, header_str, line_sep]
    for row in rows:
        res.append("| " + " | ".join(row[i].ljust(col_widths[i]) for i in range(len(row))) + " |")
    res.append(line_sep)

    if len(articles) > max_items:
        res.append(f"... and {len(articles) - max_items} more items.")
    return "\n".join(res)


def generate_obsidian_dashboard(articles: List[StagedArticle]) -> str:
    """Generates an Obsidian-native markdown dashboard with escaped pipes and clean wikilinks."""
    total = len(articles)
    staged = [a for a in articles if a.status == "STAGED"]
    drafts = [a for a in articles if a.status == "DRAFT"]
    approved = [a for a in articles if a.status == "APPROVED"]
    compiled = [a for a in articles if a.status == "COMPILED"]
    ignored = [a for a in articles if a.status == "IGNORED"]

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "---",
        'title: "News & OSINT Ingestion Staging Dashboard"',
        'type: "kanban"',
        f"last_updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "---",
        "",
        "# 📥 News & OSINT Ingestion Staging Dashboard",
        "",
        "> [!NOTE]",
        f"> **Queue Telemetry**: Total Evidence: {total} \\| ⏳ **Staged**: {len(staged)} \\| 📝 **Drafts**: {len(drafts)} \\| 🚀 **Approved**: {len(approved)} \\| ✅ **Compiled**: {len(compiled)}",
        f"> **Last Synchronized**: {now_utc}",
        "",
        "## ⏳ Staged Articles (Pending Ingestion)",
        "",
    ]

    if not staged:
        lines.append("*All harvested articles have been processed or scoped.*")
        lines.append("")
    else:
        lines.extend([
            "| # | Article Title | Wiki Link | Publisher | Lang | Date | Recommended Operational Action |",
            "| :-: | :--- | :--- | :--- | :-: | :-: | :--- |",
        ])
        for idx, a in enumerate(staged, 1):
            clean_title = a.title.replace("|", "\\|")
            stem_clean = a.filepath.stem.replace("|", "\\|")
            wiki_link = f"[[{stem_clean}]]"
            escaped_rel = str(a.filepath.relative_to(VAULT_ROOT)).replace("|", "\\|")
            action_code = f"`/ingest \"{escaped_rel}\"`"
            lines.append(f"| {idx} | {clean_title} | {wiki_link} | {a.publisher} | `{a.language}` | {a.published_date} | {action_code} |")
        lines.append("")

    lines.extend([
        "## 📝 In Review (Phase 1 Draft Source Notes)",
        "",
    ])

    if not drafts:
        lines.append("*No draft source notes currently pending review.*")
        lines.append("")
    else:
        lines.extend([
            "| # | Source Note | Associated Raw Evidence | Status | Action |",
            "| :-: | :--- | :--- | :-: | :--- |",
        ])
        for idx, a in enumerate(drafts, 1):
            source_link = f"[[sources/{a.source_note.slug}\\|{a.source_note.slug}]]" if a.source_note else "Unknown"
            raw_title = a.title.replace("|", "\\|")
            lines.append(f"| {idx} | {source_link} | {raw_title} | `draft` | Review & Approve Note |")
        lines.append("")

    lines.extend([
        "## 🚀 Approved (Ready for Phase 2 Graph Compilation)",
        "",
    ])

    if not approved:
        lines.append("*No approved source notes pending compilation.*")
        lines.append("")
    else:
        lines.extend([
            "| # | Source Note | Publisher | Date | Action |",
            "| :-: | :--- | :--- | :-: | :--- |",
        ])
        for idx, a in enumerate(approved, 1):
            source_link = f"[[sources/{a.source_note.slug}\\|{a.source_note.slug}]]" if a.source_note else "Unknown"
            compile_cmd = f"`/ingest \"wiki/sources/{a.source_note.slug}.md\"`" if a.source_note else "Ready"
            lines.append(f"| {idx} | {source_link} | {a.publisher} | {a.published_date} | {compile_cmd} |")
        lines.append("")

    lines.extend([
        "## ✅ Recently Compiled Articles",
        "",
        "| # | Source Note | Primary Evidence | Compiled Audit Dossier |",
        "| :-: | :--- | :--- | :--- |",
    ])

    for idx, a in enumerate(compiled[:15], 1):
        source_link = f"[[sources/{a.source_note.slug}\\|{a.source_note.slug}]]" if a.source_note else "Compiled"
        raw_title = a.title.replace("|", "\\|")
        dossier_link = f"[[ingestions/{a.ingestion_dossier.parent.name}/{a.ingestion_dossier.name}\\|Audit Dossier]]" if a.ingestion_dossier else "Audited"
        lines.append(f"| {idx} | {source_link} | {raw_title} | {dossier_link} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Zero-mutation staging queue & telemetry manager for harvested conflict articles in llm-wiki-news."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # Command: status
    subparsers.add_parser("status", help="Display summary telemetry of the ingestion staging queue")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List articles in the staging queue")
    list_parser.add_argument("--staged", action="store_true", help="List only uningested staged articles")
    list_parser.add_argument("--drafts", action="store_true", help="List only draft source notes in review")
    list_parser.add_argument("--approved", action="store_true", help="List only approved notes pending compilation")
    list_parser.add_argument("--compiled", action="store_true", help="List only compiled and indexed articles")
    list_parser.add_argument("--all", action="store_true", help="List all articles across all states")
    list_parser.add_argument("--limit", type=int, default=50, help="Max rows to display (default: 50)")

    # Command: next
    next_parser = subparsers.add_parser("next", help="Get the next priority staged article to ingest")
    next_parser.add_argument("--path-only", action="store_true", help="Output only the relative file path for CLI piping")
    next_parser.add_argument("--ingest-cmd", "--cmd", action="store_true", help="Output the recommended slash command (/ingest <path>)")

    # Command: sync
    sync_parser = subparsers.add_parser("sync", help="Synchronize the Obsidian staging dashboard markdown note")
    sync_parser.add_argument(
        "--output", "-o",
        default=str(DASHBOARD_FILE),
        help=f"Target path for dashboard markdown note (default: {DASHBOARD_FILE})"
    )

    args = parser.parse_args()

    # Default to 'status' if no subcommand provided
    command = args.subcommand or "status"

    articles = inspect_queue(ARTICLES_DIR, SOURCES_DIR, INGESTIONS_DIR)

    staged = [a for a in articles if a.status == "STAGED"]
    drafts = [a for a in articles if a.status == "DRAFT"]
    approved = [a for a in articles if a.status == "APPROVED"]
    compiled = [a for a in articles if a.status == "COMPILED"]
    ignored = [a for a in articles if a.status == "IGNORED"]

    if command == "status":
        print("=" * 70)
        print("  Knowledge Lab :: Ingestion Staging & Telemetry Status")
        print("=" * 70)
        print(f"  Total Harvested Articles in raw/articles/ : {len(articles)}")
        print(f"  ⏳ Staged (Pending Scoping & Ingestion)   : {len(staged)}")
        print(f"  📝 In Review (Phase 1 Draft Sources)      : {len(drafts)}")
        print(f"  🚀 Approved (Pending Graph Compilation)   : {len(approved)}")
        print(f"  ✅ Compiled & Indexed into Knowledge Base : {len(compiled)}")
        if ignored:
            print(f"  🚫 Ignored / Out of Scope                : {len(ignored)}")
        print("-" * 70)

        # Publisher breakdown for staged articles
        pub_counts: Dict[str, int] = {}
        for a in staged:
            pub_counts[a.publisher] = pub_counts.get(a.publisher, 0) + 1
        if pub_counts:
            print("  Staged Articles by Publisher:")
            for pub, count in sorted(pub_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {pub:30s} : {count:3d}")
        print("=" * 70)

    elif command == "list":
        if args.drafts:
            subset = drafts
            heading = "Articles in Phase 1 Review (Draft Sources)"
        elif args.approved:
            subset = approved
            heading = "Articles Approved for Phase 2 Graph Compilation"
        elif args.compiled:
            subset = compiled
            heading = "Compiled & Indexed Articles"
        elif args.all:
            subset = articles
            heading = "All Harvested Articles (Complete Register)"
        else:
            # Default to staged
            subset = staged
            heading = "Staged Articles (Pending Phase 1 Ingestion)"

        print(f"\n[*] {heading} ({len(subset)} items):\n")
        print(format_cli_table(subset, max_items=args.limit))

    elif command == "next":
        if not staged:
            print("[✓] Queue is clear! No staged articles pending ingestion.")
            sys.exit(0)

        # Select next candidate (oldest uningested or newest based on date)
        next_candidate = staged[0]
        rel_path = str(next_candidate.filepath.relative_to(VAULT_ROOT))

        if args.path_only:
            print(rel_path)
        elif getattr(args, "ingest_cmd", False):
            print(f'/ingest "{rel_path}"')
        else:
            print("=" * 70)
            print("  Next Article for Phase 1 Ingestion (/ingest)")
            print("=" * 70)
            print(f"  Title     : {next_candidate.title}")
            print(f"  Publisher : {next_candidate.publisher}")
            print(f"  Language  : {next_candidate.language}")
            print(f"  Date      : {next_candidate.published_date}")
            print(f"  Filepath  : {rel_path}")
            print(f"  Command   : /ingest \"{rel_path}\"")
            print("=" * 70)

    elif command == "sync":
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dashboard_content = generate_obsidian_dashboard(articles)
        out_path.write_text(dashboard_content, encoding="utf-8")
        print(f"[✓] Synchronized Obsidian Staging Dashboard to: {out_path}")
        print(f"    - Staged: {len(staged)} | Drafts: {len(drafts)} | Approved: {len(approved)} | Compiled: {len(compiled)}")


if __name__ == "__main__":
    main()
