# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/enrich_graph.py
Enriches the Neo4j knowledge graph indexed by `ki` with first-class semantic schema:
  - Purges administrative supernodes (:Folder, :Vault, :User, :INDEX, :OVERVIEW, :LOG) to prevent path short-circuiting
  - Multi-label classification (:Concept, :Entity, :Source, :Synthesis, :Ingestion)
  - Secondary glossary label (:GLOSSARY)
  - Unpacked native properties (title, type, tags, reliability_score, last_updated, in_degree)
  - Taxonomy & Glossary integration (d.aliases, d.normalized_aliases, d.acronyms, d.glossary_notes)
  - Lucene full-text search index (`doc_alias_search`) for (:Concept|Entity) with standard-folding analyzer
  - Dedicated (:Tag) nodes and [:TAGGED_WITH] graph relationships
  - Schema performance indexes and constraints

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
    print("Or install:   pip install neo4j", file=sys.stderr)
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

def generate_normalized_variants(text: str) -> List[str]:
    """Generates lowercased, umlaut-expanded, accent-stripped, and dash-normalized variants."""
    if not text:
        return []
    variants: Set[str] = set()
    text_lower = text.lower().strip()
    variants.add(text_lower)
    
    # 1. Dash and punctuation harmonization
    dash_norm = text_lower.replace("–", "-").replace("—", "-")
    variants.add(dash_norm)
    variants.add(dash_norm.replace("-", " "))
    
    # 2. German Umlaut expansion (ä -> ae, ö -> oe, ü -> ue, ß -> ss)
    umlaut_map = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    expanded = text_lower
    for k, v in umlaut_map.items():
        expanded = expanded.replace(k, v)
    variants.add(expanded)
    
    # 3. German Umlaut reverse (ae -> ä, oe -> ö, ue -> ü)
    reverse_map = {"ae": "ä", "oe": "ö", "ue": "ü"}
    reversed_str = text_lower
    for k, v in reverse_map.items():
        reversed_str = reversed_str.replace(k, v)
    variants.add(reversed_str)

    # 4. Diacritic & Accent Stripping (Unicode NFD)
    nfd = unicodedata.normalize("NFD", text_lower)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    variants.add(stripped)
    
    # 5. Clean punctuation
    clean_punct = re.sub(r"[^\w\s-]", "", text_lower)
    variants.add(clean_punct)

    # 6. Compound token extraction (for hyphenated or multi-word terms like Prüfungskultur-Wandel)
    parts = re.split(r"[\s\-_/]+", text_lower)
    if len(parts) > 1:
        for p in parts:
            if len(p) >= 3:
                variants.add(p)
                exp_p = p
                for k, v in umlaut_map.items():
                    exp_p = exp_p.replace(k, v)
                variants.add(exp_p)
                nfd_p = "".join(c for c in unicodedata.normalize("NFD", p) if unicodedata.category(c) != "Mn")
                variants.add(nfd_p)

    return sorted([v for v in variants if v])

def extract_acronyms(title: str, aliases: List[str]) -> List[str]:
    """Extracts short uppercase codes/acronyms from title and aliases."""
    acronyms = set()
    candidates = [title] + aliases
    for c in candidates:
        c_clean = c.strip()
        if 2 <= len(c_clean) <= 6 and c_clean.isupper() and c_clean.isalpha():
            acronyms.add(c_clean)
        matches = re.findall(r"\b[A-Z]{2,6}\b", c_clean)
        for m in matches:
            if m not in {"A", "AN", "THE", "AND", "OR", "NOT", "IN", "ON", "AT", "TO", "FOR", "WITH", "BY"}:
                acronyms.add(m)
    return sorted(list(acronyms))

def parse_glossary(vault_root: Path) -> Dict[str, Dict[str, Any]]:
    """Parses wiki/glossary.md table into canonical mappings."""
    glossary_path = vault_root / "wiki/glossary.md"
    if not glossary_path.exists():
        return {}
    
    mappings = {}
    content = glossary_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line[1:-1].split("|")]
            if len(cells) >= 4 and not cells[0].startswith("---") and not cells[0].startswith("Canonical"):
                canonical = cells[0]
                aliases = [a.strip() for a in cells[1].split(",") if a.strip() and a.strip() != "-"]
                disallowed = [d.strip() for d in cells[2].split(",") if d.strip() and d.strip() != "-"]
                notes = cells[3] if cells[3] != "-" else ""
                
                info = {
                    "canonical": canonical,
                    "aliases": aliases,
                    "disallowed": disallowed,
                    "notes": notes
                }
                mappings[canonical.lower()] = info
                mappings[canonical] = info
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
        # 0. Purge administrative supernodes (:Folder, :Vault, :User, :INDEX, :OVERVIEW, :LOG)
        # to prevent artificial short-circuiting in shortestPath queries and GDS community/centrality distortion.
        # (:GLOSSARY / glossary.md is preserved for taxonomy resolution).
        if not quiet:
            print("→ Purging administrative supernodes (:Folder, :Vault, :User, index.md, overview.md, log.md)...")
        session.run("DROP INDEX overview_name IF EXISTS")
        session.run("DROP INDEX log_name IF EXISTS")
        session.run("DROP INDEX index_name IF EXISTS")
        
        # Stage 1: Purge documents and their attached sections
        r_docs = session.run("""
            MATCH (d:Document)
            WHERE d.displayName IN ['index.md', 'overview.md', 'log.md']
            OPTIONAL MATCH (d)-[:HAS*1..3]->(s:Section)
            DETACH DELETE s, d
            RETURN count(d) AS docs_deleted
        """).single()
        
        # Stage 2: Purge administrative structural nodes
        r_roots = session.run("""
            MATCH (n)
            WHERE n:Folder OR n:Vault OR n:User OR n:INDEX OR n:OVERVIEW OR n:LOG
            DETACH DELETE n
            RETURN count(n) AS roots_deleted
        """).single()
        
        docs_del = r_docs["docs_deleted"] if r_docs else 0
        roots_del = r_roots["roots_deleted"] if r_roots else 0
        stats["purged_supernodes"] = docs_del + roots_del

        # 1. Create constraints and performance indexes
        if not quiet:
            print("→ Creating constraints and indexes...")
        # Check and migrate doc_alias_search if it still indexes (d:Document)
        try:
            idx_check = session.run("SHOW FULLTEXT INDEXES YIELD name, labelsOrTypes WHERE name = 'doc_alias_search' RETURN labelsOrTypes").data()
            if idx_check:
                labels = idx_check[0].get("labelsOrTypes", [])
                if "Document" in labels or set(labels) != {"Concept", "Entity"}:
                    session.run("DROP INDEX doc_alias_search IF EXISTS")
        except Exception:
            pass

        indexes = [
            "CREATE CONSTRAINT unique_tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX concept_title IF NOT EXISTS FOR (c:Concept) ON (c.title)",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX entity_title IF NOT EXISTS FOR (e:Entity) ON (e.title)",
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX researcher_title IF NOT EXISTS FOR (r:Researcher) ON (r.title)",
            "CREATE INDEX organization_title IF NOT EXISTS FOR (o:Organization) ON (o.title)",
            "CREATE INDEX software_title IF NOT EXISTS FOR (s:Software) ON (s.title)",
            "CREATE INDEX platform_title IF NOT EXISTS FOR (p:Platform) ON (p.title)",
            "CREATE INDEX source_name IF NOT EXISTS FOR (s:Source) ON (s.name)",
            "CREATE INDEX synthesis_name IF NOT EXISTS FOR (y:Synthesis) ON (y.name)",
            "CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.type)",
            "CREATE INDEX glossary_name IF NOT EXISTS FOR (g:GLOSSARY) ON (g.displayName)",
            """
            CREATE FULLTEXT INDEX doc_alias_search IF NOT EXISTS
            FOR (n:Concept|Entity)
            ON EACH [n.title, n.displayName, n.aliases, n.normalized_aliases]
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
            except Exception as e:
                # Ignore if constraint/index syntax varies by engine version
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
                        WHEN d.path CONTAINS '/concepts/' THEN 'concept'
                        WHEN d.path CONTAINS '/entities/' THEN 'entity'
                        WHEN d.path CONTAINS '/sources/' THEN 'source'
                        WHEN d.path CONTAINS '/syntheses/' THEN 'synthesis'
                        WHEN d.path CONTAINS '/ingestions/' THEN 'ingestion'
                        ELSE 'document'
                    END
                ),
                d.subtype = fm.subtype,
                d.reliability_score = toFloat(coalesce(fm.reliability_score, 1.0)),
                d.last_updated = fm.last_updated,
                d.tags = coalesce(fm.tags, []),
                d.aliases = coalesce(fm.aliases, d.aliases, [])
            RETURN count(d) AS updated
        """
        r_props = session.run(prop_query)
        stats["properties_updated"] = r_props.single()["updated"]

        # Also fallback for documents without frontmatter (e.g. index.md, overview.md)
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
            print("→ Normalizing aliases and synchronizing wiki/glossary.md taxonomy...")
        glossary = parse_glossary(VAULT_ROOT)
        
        doc_rows = session.run("""
            MATCH (d:Document)
            RETURN d.uri AS uri, d.path AS path, d.name AS name, d.displayName AS displayName, d.title AS title, d.aliases AS db_aliases
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

            # Frontmatter aliases from disk + database
            disk_aliases = parse_frontmatter_aliases_from_disk(path_str) if path_str else []
            db_aliases = r["db_aliases"] if isinstance(r.get("db_aliases"), list) else []

            # Glossary aliases
            g_info = glossary.get(title.lower()) or glossary.get(stem.lower())
            g_aliases = g_info["aliases"] if g_info else []
            g_notes = g_info["notes"] if g_info else ""

            # Merge deduplicated
            merged_aliases = list(dict.fromkeys(disk_aliases + db_aliases + g_aliases))

            # Normalized search variants
            norm_variants = set()
            for t in [title, stem] + merged_aliases:
                norm_variants.update(generate_normalized_variants(t))

            # Acronyms
            acronyms = extract_acronyms(title, merged_aliases)

            total_aliases += len(merged_aliases)
            total_norm += len(norm_variants)
            total_acronyms += len(acronyms)

            updates.append({
                "uri": uri,
                "aliases": merged_aliases,
                "normalized_aliases": sorted(list(norm_variants)),
                "acronyms": acronyms,
                "glossary_notes": g_notes
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (d:Document {uri: item.uri})
            SET d.aliases = item.aliases,
                d.normalized_aliases = item.normalized_aliases,
                d.acronyms = item.acronyms,
                d.glossary_notes = item.glossary_notes
        """, batch=updates)

        stats["total_aliases"] = total_aliases
        stats["total_normalized"] = total_norm
        stats["total_acronyms"] = total_acronyms

        # 4. Apply secondary semantic labels
        if not quiet:
            print("→ Applying domain labels (:Concept, :Entity, :Source, :Synthesis, :Ingestion)...")
        label_mappings = [
            ("concept", "Concept"),
            ("entity", "Entity"),
            ("source", "Source"),
            ("synthesis", "Synthesis"),
            ("ingestion", "Ingestion"),
        ]
        stats["labels"] = {}
        for doc_type, label in label_mappings:
            query = f"""
                MATCH (d:Document)
                WHERE d.type = $t OR d.path CONTAINS '/' + $t + 's/'
                SET d:{label}
                RETURN count(d) AS count
            """
            r_lbl = session.run(query, t=doc_type)
            stats["labels"][label] = r_lbl.single()["count"]

        # 4b. Apply secondary entity archetype labels (:Researcher, :Organization, :Software, :Platform)
        if not quiet:
            print("→ Applying entity archetype labels (:Researcher, :Organization, :Software, :Platform)...")
        session.run("MATCH (e:Entity) REMOVE e:Researcher, e:Organization, e:Software, e:Platform")

        entity_label_queries = [
            ("Researcher", """
                MATCH (e:Entity)
                WITH e, [t IN e.tags | toLower(toString(t))] AS tags
                WHERE e.subtype = 'researcher' OR (
                    e.subtype IS NULL AND (
                        (any(t IN tags WHERE t IN [
                            'researcher', 'theorist', 'author', 'creator', 'academic', 'pioneer', 
                            'psychologist', 'scientist', 'educator', 'professor', 'philosopher', 
                            'logician', 'cognitive-scientist', 'practitioner', 'founder', 
                            'humanitarian', 'inventor', 'mathematician', 'public-intellectual', 
                            'educational-psychologist', 'learning-theorist', 'historical-figure', 
                            'computer-science-pioneer'
                        ]) OR (any(t IN tags WHERE t IN ['e-learning', 'instructional-design']) AND NOT any(t IN tags WHERE t CONTAINS 'software' OR t CONTAINS 'platform')))
                        AND NOT any(t IN tags WHERE t IN ['organization', 'institution', 'ngo', 'company', 'university', 'consortium', 'non-profit', 'foundation', 'enterprise', 'school'])
                    )
                )
                SET e:Researcher, e.subtype = coalesce(e.subtype, 'researcher')
                RETURN count(e) AS count
            """),
            ("Organization", """
                MATCH (e:Entity)
                WHERE NOT e:Researcher
                WITH e, [t IN e.tags | toLower(toString(t))] AS tags
                WHERE e.subtype = 'organization' OR (
                    e.subtype IS NULL AND any(t IN tags WHERE t IN [
                        'organization', 'institution', 'ngo', 'company', 'university', 
                        'consortium', 'non-profit', 'foundation', 'enterprise', 'school', 'initiative', 'screenlab'
                    ])
                )
                SET e:Organization, e.subtype = coalesce(e.subtype, 'organization')
                RETURN count(e) AS count
            """),
            ("Software", """
                MATCH (e:Entity)
                WHERE NOT e:Researcher AND NOT e:Organization
                WITH e, [t IN e.tags | toLower(toString(t))] AS tags
                WHERE e.subtype = 'software' OR (
                    e.subtype IS NULL AND any(t IN tags WHERE t IN [
                        'software', 'library', 'model', 'tool', 'database', 'graph-database', 
                        'infrastructure', 'ai-model', 'ssg', 'framework', 'lms', 'ai-evaluation', 
                        'benchmarks', 'software-platform', 'ai-infrastructure', 'cloud-infrastructure', 
                        'developer-tools', 'api-gateway', 'martech'
                    ])
                )
                SET e:Software, e.subtype = coalesce(e.subtype, 'software')
                RETURN count(e) AS count
            """),
            ("Platform", """
                MATCH (e:Entity)
                WHERE NOT e:Researcher AND NOT e:Organization AND NOT e:Software
                WITH e, [t IN e.tags | toLower(toString(t))] AS tags
                WHERE e.subtype = 'platform' OR (
                    e.subtype IS NULL AND any(t IN tags WHERE t IN [
                        'platform', 'media', 'social-media', 'video-platform', 'network'
                    ])
                )
                SET e:Platform, e.subtype = coalesce(e.subtype, 'platform')
                RETURN count(e) AS count
            """),
        ]
        stats["entity_archetypes"] = {}
        for arch_label, query_str in entity_label_queries:
            r_arch = session.run(query_str)
            stats["entity_archetypes"][arch_label] = r_arch.single()["count"]

        # 4c. Apply glossary secondary label (:GLOSSARY)
        if not quiet:
            print("→ Applying glossary secondary label (:GLOSSARY)...")
        r_root = session.run(
            'MATCH (n:Document) WHERE n.displayName = "glossary.md" SET n:GLOSSARY RETURN count(n) AS count'
        )
        stats["root_labels"] = {"GLOSSARY": r_root.single()["count"]}

        # 5. Synchronize (:Tag) nodes and [:TAGGED_WITH] relationships
        if not quiet:
            print("→ Synchronizing (:Tag) nodes and [:TAGGED_WITH] relationships...")
        # Clear stale tag relationships
        session.run("MATCH (:Document)-[r:TAGGED_WITH]->(:Tag) DELETE r")
        session.run("MATCH (t:Tag) WHERE NOT ()-[:TAGGED_WITH]->(t) DELETE t")

        # Materialize tags
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
        session.run("MATCH (s:CognitiveStep) REMOVE s:CognitiveStep")

        # Canonical concept lead anchor (:Summary) and Core Thesis (:CoreThesis)
        r_sum = session.run("""
            MATCH (d:Concept)-[:HAS*1..2]->(s:Section)
            WHERE s.step_type = 'DEFINITIONAL_ANCHOR'
               OR s.content CONTAINS '[!IMPORTANT] Definitional Anchor'
               OR s.displayName = d.title
            SET s:DefinitionalAnchor, s:Summary
            RETURN count(s) AS count
        """).single()

        r_th = session.run("""
            MATCH (d:Concept)-[:HAS*1..2]->(s:Section)
            WHERE s.step_type = 'CORE_THESIS'
               OR toLower(s.displayName) =~ '.*1[\\.:]\\s*core thesis.*'
            SET s:DefinitionalAnchor, s:CoreThesis
            RETURN count(s) AS count
        """).single()

        section_label_mappings = [
            ("PRESCRIPTIVE_SOLUTION", "PrescriptiveSolution", r".*(solution|mitigat|safeguard|countermeasure|counter-architecture|counter-measure|remedy|intervention|protocol|governance|repayment|action|defense).*"),
            ("DILEMMA_PROBLEM", "DilemmaProblem", r".*(tension|paradox|problem|crisis|challenge|gap|dilemma|anomaly|threat|blindspot|vulnerability|friction).*"),
            ("MANIFESTATION_TRAP", "ManifestationTrap", r".*(trap|failure|misattribution|illusion|collapse|offloading|fatigue|debt|pathology|symptom|manifestation|backlash).*"),
            ("EMPIRICAL_BOUNDARY", "EmpiricalBoundary", r".*(boundary|exception|rebuttal|contradiction|tension|debate|limitation|constraint|risk).*"),
            ("SYNTHESIS_CATALOG", "SynthesisCatalog", r".*(related notes|references|see also|further reading|citations|bibliography).*"),
            ("MECHANISTIC_DEEPEN", "MechanisticDeepen", r".*(mechanism|anatomy|engine|underlying|process|driver|loop|dynamics|architecture|operational|structural).*"),
        ]
        stats["section_labels"] = {
            "Summary": r_sum["count"],
            "CoreThesis": r_th["count"]
        }
        for step_type, label, pattern in section_label_mappings:
            query = f"""
                MATCH (d:Document)-[:HAS*1..3]->(s:Section)
                WHERE s.step_type = $st
                   OR (s.step_type IS NULL 
                       AND NOT s.displayName = d.title 
                       AND NOT s.content CONTAINS '[!IMPORTANT] Definitional Anchor'
                       AND toLower(coalesce(s.displayName, s.name, '')) =~ $pat)
                SET s:{label}
                RETURN count(s) AS count
            """
            r_sec = session.run(query, st=step_type, pat=pattern)
            stats["section_labels"][label] = r_sec.single()["count"]

    stats["elapsed_sec"] = round(time.time() - start_time, 3)
    return stats

def main():
    parser = argparse.ArgumentParser(description="Enrich Neo4j graph with semantic labels, tags, and glossary aliases.")
    parser.add_argument("--uri", default=DEFAULT_URI, help=f"Neo4j Bolt URI (default: {DEFAULT_URI})")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"Neo4j username (default: {DEFAULT_USER})")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress operational logs")
    args = parser.parse_args()

    driver = get_driver(args.uri, args.user, args.password)
    try:
        stats = enrich_schema(driver, database=args.database, quiet=args.quiet)
        print("\n✅ Knowledge Graph Schema Enrichment Complete!")
        print(f"⏱  Execution Time: {stats['elapsed_sec']}s")
        if stats.get("purged_supernodes", 0) > 0:
            print(f"🧹 Purged Supernodes: {stats['purged_supernodes']} administrative nodes removed (:Folder, :Vault, :User, :INDEX, :OVERVIEW, :LOG)")
        print(f"📄 Unpacked Documents: {stats['properties_updated']}")
        print(f"🏷  Semantic Labels:")
        for label, count in stats["labels"].items():
            print(f"    • :{label:<10} → {count} nodes")
        print(f"🔤 Aliases Materialized: {stats['total_aliases']} aliases across {stats['total_normalized']} normalized search keys ({stats['total_acronyms']} acronyms)")
        print(f"🔖 Tags Materialized: {stats['tags_created']} (:Tag) nodes ({stats['tag_links_created']} [:TAGGED_WITH] links)")
        print(f"📊 Citations Counted: {stats['docs_counted']} documents updated with .in_degree")
        if "entity_archetypes" in stats:
            print(f"👥 Entity Archetype Labels:")
            for label, count in stats["entity_archetypes"].items():
                print(f"    • :{label:<14} → {count} entities")
        if "section_labels" in stats:
            print(f"📑 Section Epistemic Labels:")
            for label, count in stats["section_labels"].items():
                print(f"    • :{label:<22} → {count} sections")
    finally:
        driver.close()

if __name__ == "__main__":
    main()
