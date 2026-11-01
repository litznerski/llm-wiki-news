# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/enrich_graph.py
Enriches the Neo4j knowledge graph indexed by `ki` with the Sudan News & OSINT semantic schema:
  - Purges administrative supernodes (:Folder, :Vault, :User, :INDEX, :OVERVIEW, :LOG) to prevent path short-circuiting
  - Multi-label classification (:Event, :Actor, :Location, :Theme, :Timeline, :Source, :Synthesis, :Ingestion)
    plus backward-compatible secondary labels (:Concept on :Event|:Theme, :Entity on :Actor|:Location)
  - Actor & Location archetype labels (:StateForce, :ArmedGroup, :PoliticalBody, :CivilSociety, :Person, :MediaSource,
    :StateADM1, :LocalityADM2, :CityTown, :IDPCamp, :BorderCrossing, :Infrastructure)
  - Unpacked native properties (title, type, subtype, event_category, event_start_date, pcode, admiralty_rating,
    reliability_score, fatalities_best, current_control, last_updated, in_degree)
  - Cross-lingual Arabic/English/French & UN OCHA P-Code normalization from wiki/glossary.md
  - Lucene full-text search index (`doc_alias_search`) with standard-folding analyzer
  - Dedicated (:Tag) nodes and [:TAGGED_WITH] graph relationships

Usage:
    uv run scripts/enrich_graph.py
    python3 scripts/enrich_graph.py [--uri bolt://localhost:7687] [--user neo4j] [--password password]
"""

import os
import sys
import time
import json
import re
import unicodedata
import argparse
from pathlib import Path
from typing import Dict, Any, List, Set

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/enrich_graph.py", file=sys.stderr)
    sys.exit(1)

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

DEFAULT_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DEFAULT_USER = os.getenv("NEO4J_USER", "neo4j")
DEFAULT_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DEFAULT_DATABASE = os.getenv("NEO4J_DATABASE")


def normalize_arabic(text: str) -> str:
    """Normalizes Arabic script variants (Alef forms, Teh Marbuta, Alef Maksura, Tatweel, diacritics)."""
    if not text:
        return ""
    # Strip harakat / tashkeel and tatweel
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    # Normalize Alef variants (أ إ آ ٱ -> ا)
    text = re.sub(r"[أإآٱ]", "ا", text)
    # Normalize Teh Marbuta (ة -> ه) and Alef Maksura (ى -> ي)
    text = text.replace("ة", "ه").replace("ى", "ي")
    return text


def generate_normalized_variants(text: str) -> List[str]:
    """Generates lowercased, Arabic-normalized, accent-stripped, and dash-normalized variants."""
    if not text:
        return []
    variants: Set[str] = set()
    text_clean = text.strip().strip("`")
    text_lower = text_clean.lower()
    variants.add(text_lower)

    # 1. Arabic script normalization
    ar_norm = normalize_arabic(text_lower)
    if ar_norm:
        variants.add(ar_norm)
        # Also strip "ال" (Al-) definite article prefix on Arabic words
        variants.add(re.sub(r"\bال", "", ar_norm))

    # 2. English/French transliteration prefix normalization (Al-, El-, Ad-, Ash-, An-)
    translit_norm = re.sub(r"\b(al|el|ad|ash|an|as)[\-\s]+", "", text_lower)
    if translit_norm:
        variants.add(translit_norm)

    # 3. Dash and punctuation harmonization
    dash_norm = text_lower.replace("–", "-").replace("—", "-")
    variants.add(dash_norm)
    variants.add(dash_norm.replace("-", " "))

    # 4. Diacritic & Accent Stripping (Unicode NFD)
    nfd = unicodedata.normalize("NFD", text_lower)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    variants.add(stripped)

    # 5. Clean punctuation
    clean_punct = re.sub(r"[^\w\s-]", "", text_lower)
    variants.add(clean_punct)

    # 6. Compound token extraction
    parts = re.split(r"[\s\-_/]+", text_lower)
    if len(parts) > 1:
        for p in parts:
            if len(p) >= 3:
                variants.add(p)

    return sorted([v for v in variants if v])


def extract_acronyms(title: str, aliases: List[str]) -> List[str]:
    """Extracts short uppercase codes/acronyms and UN OCHA P-Codes (e.g., SAF, RSF, SD02001)."""
    acronyms = set()
    candidates = [title] + aliases
    for c in candidates:
        c_clean = c.strip().strip("`")
        if 2 <= len(c_clean) <= 8 and c_clean.isupper() and any(ch.isalpha() for ch in c_clean):
            acronyms.add(c_clean)
        matches = re.findall(r"\b(?:SD\d{2,6}|[A-Z]{2,6}(?:-[A-Z]{1,3})?)\b", c_clean)
        for m in matches:
            if m not in {"A", "AN", "THE", "AND", "OR", "NOT", "IN", "ON", "AT", "TO", "FOR", "WITH", "BY"}:
                acronyms.add(m)
    return sorted(list(acronyms))


def parse_glossary(vault_root: Path) -> Dict[str, Dict[str, Any]]:
    """Parses wiki/glossary.md tables (both Actors and UN OCHA P-Code Locations) into canonical mappings."""
    glossary_path = vault_root / "wiki/glossary.md"
    if not glossary_path.exists():
        return {}

    mappings = {}
    content = glossary_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|") and not line.startswith("| :---"):
            cells = [c.strip() for c in line[1:-1].split("|")]
            if len(cells) >= 4 and cells[0] not in ("Term / Primary Acronym", "UN OCHA P-Code", "Term", "Canonical Concept / Entity"):
                col0 = cells[0].replace("**", "").strip()
                col1 = re.sub(r"^\[\[|\]\]$", "", cells[1].strip())
                raw_aliases = [a.strip().strip("`") for a in cells[2].split(",") if a.strip() and a.strip() != "-"]
                notes = cells[3] if cells[3] != "-" else ""

                # Support both new 4-col Sudan glossary (Col0=Term/PCode, Col1=[[Canonical]]) and legacy format
                canonical = col1 if col1 else col0
                aliases = [col0] + raw_aliases if col0 and col0 != canonical else raw_aliases
                pcode = col0 if re.match(r"^SD\d+$", col0) else ""

                info = {
                    "canonical": canonical,
                    "aliases": list(dict.fromkeys(aliases)),
                    "pcode": pcode,
                    "notes": notes
                }
                mappings[canonical.lower()] = info
                mappings[canonical] = info
                if col0:
                    mappings[col0.lower()] = info
    return mappings


def parse_frontmatter_aliases_from_disk(file_path_str: str) -> List[str]:
    """Reads frontmatter aliases directly from disk markdown file."""
    if not file_path_str:
        return []
    p = Path(file_path_str)
    if not p.exists() or not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8")
        if text.startswith("---"):
            end_idx = text.find("---", 3)
            if end_idx != -1:
                fm_text = text[3:end_idx]
                for line in fm_text.splitlines():
                    line = line.strip()
                    if line.startswith("aliases:"):
                        val = line[len("aliases:"):].strip()
                        if val.startswith("[") and val.endswith("]"):
                            items = [i.strip().strip("'\"") for i in val[1:-1].split(",") if i.strip()]
                            return items
    except Exception:
        pass
    return []


def get_driver(uri: str, user: str, password: str) -> Driver:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        print(f"Error connecting to Neo4j at {uri}: {e}", file=sys.stderr)
        sys.exit(1)


def enrich_schema(driver: Driver, database: str = None, quiet: bool = False) -> Dict[str, Any]:
    stats = {}
    start_time = time.time()

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        if not quiet:
            print("→ Purging administrative supernodes (:Folder, :Vault, :User, index.md, overview.md, log.md)...")
        session.run("DROP INDEX overview_name IF EXISTS")
        session.run("DROP INDEX log_name IF EXISTS")
        session.run("DROP INDEX index_name IF EXISTS")

        r_docs = session.run("""
            MATCH (d:Document)
            WHERE d.displayName IN ['index.md', 'overview.md', 'log.md']
            OPTIONAL MATCH (d)-[:HAS*1..3]->(s:Section)
            DETACH DELETE s, d
            RETURN count(d) AS docs_deleted
        """).single()

        r_roots = session.run("""
            MATCH (n)
            WHERE n:Folder OR n:Vault OR n:User OR n:INDEX OR n:OVERVIEW OR n:LOG
            DETACH DELETE n
            RETURN count(n) AS roots_deleted
        """).single()

        docs_del = r_docs["docs_deleted"] if r_docs else 0
        roots_del = r_roots["roots_deleted"] if r_roots else 0
        stats["purged_supernodes"] = docs_del + roots_del

        if not quiet:
            print("→ Creating constraints and indexes for Sudan News & OSINT schema...")
        try:
            session.run("DROP INDEX doc_alias_search IF EXISTS")
        except Exception:
            pass

        indexes = [
            "CREATE CONSTRAINT unique_tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX event_title IF NOT EXISTS FOR (e:Event) ON (e.title)",
            "CREATE INDEX event_start_date IF NOT EXISTS FOR (e:Event) ON (e.event_start_date)",
            "CREATE INDEX event_pcode IF NOT EXISTS FOR (e:Event) ON (e.pcode)",
            "CREATE INDEX actor_title IF NOT EXISTS FOR (a:Actor) ON (a.title)",
            "CREATE INDEX location_title IF NOT EXISTS FOR (l:Location) ON (l.title)",
            "CREATE INDEX location_pcode IF NOT EXISTS FOR (l:Location) ON (l.pcode)",
            "CREATE INDEX theme_title IF NOT EXISTS FOR (t:Theme) ON (t.title)",
            "CREATE INDEX timeline_title IF NOT EXISTS FOR (t:Timeline) ON (t.title)",
            "CREATE INDEX source_name IF NOT EXISTS FOR (s:Source) ON (s.name)",
            "CREATE INDEX synthesis_name IF NOT EXISTS FOR (y:Synthesis) ON (y.name)",
            "CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.type)",
            "CREATE INDEX glossary_name IF NOT EXISTS FOR (g:GLOSSARY) ON (g.displayName)",
            """
            CREATE FULLTEXT INDEX doc_alias_search IF NOT EXISTS
            FOR (n:Event|Actor|Location|Theme|Concept|Entity)
            ON EACH [n.title, n.displayName, n.aliases, n.normalized_aliases, n.pcode]
            OPTIONS {
                indexConfig: {
                    `fulltext.analyzer`: 'standard-folding'
                }
            }
            """,
        ]
        for idx_query in indexes:
            try:
                session.run(idx_query)
            except Exception:
                pass

        # 2. Unpack frontmatter properties onto (d:Document)
        if not quiet:
            print("→ Unpacking frontmatter JSON properties...")
        prop_query = """
            MATCH (d:Document)
            WHERE d.frontmatter IS NOT NULL
            WITH d, apoc.convert.fromJsonMap(d.frontmatter) AS fm
            SET d.title = coalesce(fm.title, replace(d.displayName, '.md', '')),
                d.type = coalesce(fm.type,
                    CASE
                        WHEN d.path CONTAINS '/events/' THEN 'event'
                        WHEN d.path CONTAINS '/actors/' THEN 'actor'
                        WHEN d.path CONTAINS '/locations/' THEN 'location'
                        WHEN d.path CONTAINS '/themes/' THEN 'theme'
                        WHEN d.path CONTAINS '/timelines/' THEN 'timeline'
                        WHEN d.path CONTAINS '/sources/' THEN 'source'
                        WHEN d.path CONTAINS '/syntheses/' THEN 'synthesis'
                        WHEN d.path CONTAINS '/ingestions/' THEN 'ingestion'
                        ELSE 'document'
                    END
                ),
                d.subtype = fm.subtype,
                d.event_category = fm.event_category,
                d.event_sub_type = fm.event_sub_type,
                d.event_start_date = toString(fm.event_start_date),
                d.event_end_date = toString(fm.event_end_date),
                d.reported_date = toString(fm.reported_date),
                d.pcode = fm.pcode,
                d.geo_precision = fm.geo_precision,
                d.fatalities_low = toInteger(fm.fatalities_low),
                d.fatalities_best = toInteger(fm.fatalities_best),
                d.fatalities_high = toInteger(fm.fatalities_high),
                d.verification_status = fm.verification_status,
                d.admiralty_rating = fm.admiralty_rating,
                d.reliability_score = toFloat(coalesce(fm.reliability_score, 0.85)),
                d.contradiction_flags = coalesce(fm.contradiction_flags, []),
                d.current_control = fm.current_control,
                d.humanitarian_ipc_phase = toInteger(fm.humanitarian_ipc_phase),
                d.acled_actor_type = fm.acled_actor_type,
                d.alignment = fm.alignment,
                d.language = fm.language,
                d.last_updated = toString(fm.last_updated),
                d.tags = coalesce(fm.tags, []),
                d.aliases = coalesce(fm.aliases, d.aliases, [])
            RETURN count(d) AS updated
        """
        r_props = session.run(prop_query)
        stats["properties_updated"] = r_props.single()["updated"]

        session.run("""
            MATCH (d:Document)
            WHERE d.frontmatter IS NULL
            SET d.title = coalesce(d.title, replace(d.displayName, '.md', '')),
                d.type = coalesce(d.type, 'meta'),
                d.subtype = null,
                d.tags = coalesce(d.tags, []),
                d.aliases = coalesce(d.aliases, [])
        """)

        # 3. Synchronize Glossary taxonomy and compute normalized aliases & acronyms
        if not quiet:
            print("→ Normalizing Arabic/English aliases and synchronizing wiki/glossary.md...")
        glossary = parse_glossary(VAULT_ROOT)

        doc_rows = session.run("""
            MATCH (d:Document)
            RETURN d.uri AS uri, d.path AS path, d.name AS name, d.displayName AS displayName,
                   d.title AS title, d.aliases AS db_aliases, d.pcode AS pcode
        """).data()

        updates = []
        total_aliases = 0
        total_norm = 0
        total_acronyms = 0

        for r in doc_rows:
            uri = r["uri"]
            path_str = r.get("path")
            title = r.get("title") or ""
            display_name = r.get("displayName") or r.get("name") or ""
            stem = display_name.replace(".md", "")
            if not title:
                title = stem

            disk_aliases = parse_frontmatter_aliases_from_disk(path_str) if path_str else []
            db_aliases = r["db_aliases"] if isinstance(r.get("db_aliases"), list) else []

            g_info = glossary.get(title.lower()) or glossary.get(stem.lower())
            g_aliases = g_info["aliases"] if g_info else []
            g_notes = g_info["notes"] if g_info else ""
            g_pcode = g_info.get("pcode", "") if g_info else ""
            effective_pcode = r.get("pcode") or g_pcode

            merged_aliases = list(dict.fromkeys(disk_aliases + db_aliases + g_aliases))
            if effective_pcode and effective_pcode not in merged_aliases:
                merged_aliases.append(effective_pcode)

            norm_variants = set()
            for t in [title, stem] + merged_aliases:
                norm_variants.update(generate_normalized_variants(t))

            acronyms = extract_acronyms(title, merged_aliases)

            total_aliases += len(merged_aliases)
            total_norm += len(norm_variants)
            total_acronyms += len(acronyms)

            updates.append({
                "uri": uri,
                "aliases": merged_aliases,
                "normalized_aliases": sorted(list(norm_variants)),
                "acronyms": acronyms,
                "pcode": effective_pcode,
                "glossary_notes": g_notes
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (d:Document {uri: item.uri})
            SET d.aliases = item.aliases,
                d.normalized_aliases = item.normalized_aliases,
                d.acronyms = item.acronyms,
                d.pcode = coalesce(d.pcode, item.pcode),
                d.glossary_notes = item.glossary_notes
        """, batch=updates)

        stats["total_aliases"] = total_aliases
        stats["total_normalized"] = total_norm
        stats["total_acronyms"] = total_acronyms

        # 4. Apply primary & compatibility domain labels
        if not quiet:
            print("→ Applying Sudan News domain labels (:Event, :Actor, :Location, :Theme, :Timeline, :Source, :Synthesis, :Ingestion)...")
        label_mappings = [
            ("event", "Event", "Concept"),
            ("actor", "Actor", "Entity"),
            ("location", "Location", "Entity"),
            ("theme", "Theme", "Concept"),
            ("timeline", "Timeline", "Concept"),
            ("source", "Source", None),
            ("synthesis", "Synthesis", None),
            ("ingestion", "Ingestion", None),
        ]
        stats["labels"] = {}
        for doc_type, primary_label, compat_label in label_mappings:
            set_clause = f"SET d:{primary_label}" + (f", d:{compat_label}" if compat_label else "")
            query = f"""
                MATCH (d:Document)
                WHERE d.type = $t OR d.path CONTAINS '/' + $t + 's/'
                {set_clause}
                RETURN count(d) AS count
            """
            r_lbl = session.run(query, t=doc_type)
            stats["labels"][primary_label] = r_lbl.single()["count"]

        # 4b. Apply secondary Actor & Location archetype labels
        if not quiet:
            print("→ Applying Actor & Location subtype labels...")
        archetype_mappings = [
            ("Actor", "state_force", "StateForce"),
            ("Actor", "armed_group", "ArmedGroup"),
            ("Actor", "political_body", "PoliticalBody"),
            ("Actor", "civil_society", "CivilSociety"),
            ("Actor", "person", "Person"),
            ("Actor", "media_source", "MediaSource"),
            ("Location", "state_adm1", "StateADM1"),
            ("Location", "locality_adm2", "LocalityADM2"),
            ("Location", "city_town", "CityTown"),
            ("Location", "neighborhood_site", "NeighborhoodSite"),
            ("Location", "idp_camp", "IDPCamp"),
            ("Location", "infrastructure", "Infrastructure"),
            ("Location", "border_crossing", "BorderCrossing"),
        ]
        stats["archetypes"] = {}
        for base_lbl, subtype_val, sub_lbl in archetype_mappings:
            r_sub = session.run(f"""
                MATCH (n:{base_lbl})
                WHERE n.subtype = $st
                SET n:{sub_lbl}
                RETURN count(n) AS count
            """, st=subtype_val).single()
            cnt = r_sub["count"] if r_sub else 0
            if cnt > 0:
                stats["archetypes"][sub_lbl] = cnt

        # 4c. Apply glossary secondary label (:GLOSSARY)
        r_root = session.run(
            'MATCH (n:Document) WHERE n.displayName = "glossary.md" SET n:GLOSSARY RETURN count(n) AS count'
        )
        stats["root_labels"] = {"GLOSSARY": r_root.single()["count"]}

        # 5. Synchronize (:Tag) nodes and [:TAGGED_WITH] relationships
        if not quiet:
            print("→ Synchronizing (:Tag) nodes and [:TAGGED_WITH] relationships...")
        session.run("MATCH (:Document)-[r:TAGGED_WITH]->(:Tag) DELETE r")
        session.run("MATCH (t:Tag) WHERE NOT ()-[:TAGGED_WITH]->(t) DELETE t")

        tag_query = """
            MATCH (d:Document)
            WHERE d.tags IS NOT NULL AND size(d.tags) > 0
            UNWIND d.tags AS raw_tag
            WITH d, toLower(trim(toString(raw_tag))) AS tag_name
            WHERE tag_name <> ''
            MERGE (t:Tag {name: tag_name})
            MERGE (d)-[:TAGGED_WITH]->(t)
            RETURN count(DISTINCT t) AS total_tags, count(*) AS total_links
        """
        r_tags = session.run(tag_query)
        tag_record = r_tags.single()
        stats["tags_created"] = tag_record["total_tags"]
        stats["tag_links_created"] = tag_record["total_links"]

        # 6. Calculate and materialize citation in_degree
        if not quiet:
            print("→ Materializing citation in_degree on documents...")
        deg_query = """
            MATCH (d:Document)
            OPTIONAL MATCH (:Section)-[r:LINKS_TO]->(d)
            WITH d, count(r) AS in_degree
            SET d.in_degree = in_degree
            RETURN count(d) AS docs_counted
        """
        r_deg = session.run(deg_query)
        stats["docs_counted"] = r_deg.single()["docs_counted"]

        # 7. Materialize secondary epistemic labels on (:Section) nodes
        if not quiet:
            print("→ Materializing secondary epistemic labels on (:Section) nodes...")
        section_label_mappings = [
            ("EVENT_ANCHOR", "EventAnchor", r".*(event anchor|5w1h summary|5w1h event).*"),
            ("CHRONOLOGICAL_MECHANICS", "ChronologicalMechanics", r".*(chronological sequence|tactical mechanics|what & how).*"),
            ("CAUSAL_MOTIVES", "CausalMotives", r".*(causal drivers|strategic motives|why).*"),
            ("IMPACT_ASSESSMENT", "ImpactAssessment", r".*(humanitarian|territorial|geopolitical impact|consequences).*"),
            ("CONTRADICTION_MATRIX", "ContradictionMatrix", r".*(competing narratives|attribution|contradictions|disputes).*"),
            ("SYNTHESIS_CATALOG", "SynthesisCatalog", r".*(related primitives|related notes|references|see also).*"),
        ]
        stats["section_labels"] = {}
        for step_type, label, pattern in section_label_mappings:
            query = f"""
                MATCH (d:Document)-[:HAS*1..3]->(s:Section)
                WHERE s.step_type = $st
                   OR toLower(coalesce(s.displayName, s.name, '')) =~ $pat
                SET s:{label}
                RETURN count(s) AS count
            """
            r_sec = session.run(query, st=step_type, pat=pattern)
            stats["section_labels"][label] = r_sec.single()["count"]

    stats["elapsed_sec"] = round(time.time() - start_time, 3)
    return stats


def main():
    parser = argparse.ArgumentParser(description="Enrich Neo4j graph with Sudan News labels, tags, P-Codes, and glossary aliases.")
    parser.add_argument("--uri", default=DEFAULT_URI, help=f"Neo4j Bolt URI (default: {DEFAULT_URI})")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"Neo4j username (default: {DEFAULT_USER})")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress operational logs")
    args = parser.parse_args()

    driver = get_driver(args.uri, args.user, args.password)
    try:
        stats = enrich_schema(driver, database=args.database, quiet=args.quiet)
        print("\n✅ Sudan News & OSINT Graph Schema Enrichment Complete!")
        print(f"⏱  Execution Time: {stats['elapsed_sec']}s")
        print(f"📄 Unpacked Documents: {stats['properties_updated']}")
        print(f"🏷  Domain Labels:")
        for label, count in stats["labels"].items():
            print(f"    • :{label:<10} → {count} nodes")
        print(f"🔤 Aliases Materialized: {stats['total_aliases']} aliases across {stats['total_normalized']} normalized search keys ({stats['total_acronyms']} codes/acronyms)")
        print(f"🔖 Tags Materialized: {stats['tags_created']} (:Tag) nodes ({stats['tag_links_created']} [:TAGGED_WITH] links)")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
