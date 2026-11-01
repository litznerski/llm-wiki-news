# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/extract_entity_cot.py
Extracts and materializes Sudan News & OSINT Actor and Location Arcs (plus legacy Entity Arcs) into Neo4j:
  - Micro-CoT: Classifies Actor and Location sections into canonical 6-stage intelligence steps:
      * Actor (wiki/actors/):
          1. ACTOR_ANCHOR          (1. Identity, Classification & Leadership Anchor)
          2. COMMAND_LINEAGE       (2. Historical Lineage, Factions & Command Structure)
          3. STRATEGIC_DOCTRINE    (3. Strategic Objectives, Ideology & Political Economy)
          4. ALLIANCE_NETWORK      (4. Operational Capabilities, Alliances & Foreign Backing)
          5. EVENT_FOOTPRINT       (5. Chronological Event Footprint & Accountability Record)
          6. SYNTHESIS_CATALOG     (Related Primitives)
      * Location (wiki/locations/):
          1. LOCATION_ANCHOR          (1. Geopolitical Identity & Strategic Significance)
          2. TERRITORIAL_CONTROL      (2. Territorial Control History & Armed Presence)
          3. INFRASTRUCTURE_LOGISTICS (3. Key Infrastructure, Trade Corridors & Resources)
          4. HUMANITARIAN_STATUS      (4. Humanitarian Status, Displacement & Civil Services)
          5. EVENT_LOG                (5. Chronological Log of Major Conflict Events)
          6. SYNTHESIS_CATALOG        (Related Primitives)
  - Macro-CoT: Discovers and materializes Actor & Location agency/spatial relationships in Neo4j:
      * [:COMMANDED_BY]       (Actor -> Actor)
      * [:ALLIED_WITH]        (Actor -> Actor)
      * [:SPONSORED_BY]       (Actor -> Actor)
      * [:DEFECTED_TO]        (Actor -> Actor)
      * [:CONTROLS_TERRITORY] (Actor -> Location)
      * [:LOCATED_IN]         (Location -> Location)
      * [:PUBLISHED_BY]       (Source -> Actor)

Usage:
    uv run scripts/extract_entity_cot.py
    python3 scripts/extract_entity_cot.py
"""

import os
import sys
import time
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/extract_entity_cot.py", file=sys.stderr)
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

# --- Actor & Location Archetype Heading Patterns ---

PATTERNS_ACTOR = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(1\.\s*identity|classification|leadership anchor|identity|actor anchor|profile|overview)", "ACTOR_ANCHOR"),
    (r"(2\.\s*historical lineage|factions|command structure|command lineage|order of battle|hierarchy)", "COMMAND_LINEAGE"),
    (r"(3\.\s*strategic objectives|ideology|political economy|strategic doctrine|revenue|war economy)", "STRATEGIC_DOCTRINE"),
    (r"(4\.\s*operational capabilities|alliances|foreign backing|alliance network|weapons|Coalition)", "ALLIANCE_NETWORK"),
    (r"(5\.\s*chronological event footprint|accountability record|event footprint|major battles|sanctions)", "EVENT_FOOTPRINT"),
]

PATTERNS_LOCATION = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(1\.\s*geopolitical identity|strategic significance|location anchor|p-code|administrative)", "LOCATION_ANCHOR"),
    (r"(2\.\s*territorial control|armed presence|control history|garrison|frontline)", "TERRITORIAL_CONTROL"),
    (r"(3\.\s*key infrastructure|trade corridors|resources|infrastructure|airports|bridges|gold|oil)", "INFRASTRUCTURE_LOGISTICS"),
    (r"(4\.\s*humanitarian status|displacement|civil services|ipc phase|famine|idp|hospitals)", "HUMANITARIAN_STATUS"),
    (r"(5\.\s*chronological log|major conflict events|event log|timeline of events)", "EVENT_LOG"),
]

PATTERNS_RESEARCHER = [
    (r"(related primitives|related notes|references|see also|citations)", "SYNTHESIS_CATALOG"),
    (r"(epistemic role|core thesis|thesis anchor|biographical|profile|overview)", "EPISTEMIC_ANCHOR"),
    (r"(intellectual lineage|theoretical foundation|academic background|career|lineage)", "INTELLECTUAL_LINEAGE"),
    (r"(contested paradigm|dialectical critique|critique|rebuttal|debates)", "DIALECTICAL_CRITIQUE"),
    (r"(canonical formulation|methodological model|model|principles|framework)", "CANONICAL_MODEL"),
    (r"(pedagogical deployment|application|deployment in|role in knowledge)", "PEDAGOGICAL_DEPLOYMENT"),
]


def classify_entity_heading(heading_text: str, domain_type: str, archetype: str, doc_title: str) -> str:
    """Classifies an Actor, Location, or legacy Entity section heading into its canonical Micro-CoT step."""
    if not heading_text:
        return "NARRATIVE_STEP"

    h_lower = heading_text.lower().strip()

    if h_lower == doc_title.lower().strip():
        if domain_type == "location":
            return "LOCATION_ANCHOR"
        elif domain_type == "actor":
            return "ACTOR_ANCHOR"
        return "EPISTEMIC_ANCHOR"

    if re.search(r"(related primitives|related notes|references|see also)", h_lower):
        return "SYNTHESIS_CATALOG"

    if domain_type == "location":
        for pat, step_type in PATTERNS_LOCATION:
            if re.search(pat, h_lower):
                return step_type
        m = re.match(r"^(\d+)\.", h_lower)
        if m:
            mapping = {
                1: "LOCATION_ANCHOR",
                2: "TERRITORIAL_CONTROL",
                3: "INFRASTRUCTURE_LOGISTICS",
                4: "HUMANITARIAN_STATUS",
                5: "EVENT_LOG",
                6: "SYNTHESIS_CATALOG",
            }
            return mapping.get(int(m.group(1)), "NARRATIVE_STEP")

    if domain_type == "actor":
        for pat, step_type in PATTERNS_ACTOR:
            if re.search(pat, h_lower):
                return step_type
        m = re.match(r"^(\d+)\.", h_lower)
        if m:
            mapping = {
                1: "ACTOR_ANCHOR",
                2: "COMMAND_LINEAGE",
                3: "STRATEGIC_DOCTRINE",
                4: "ALLIANCE_NETWORK",
                5: "EVENT_FOOTPRINT",
                6: "SYNTHESIS_CATALOG",
            }
            return mapping.get(int(m.group(1)), "NARRATIVE_STEP")

    for pat, step_type in PATTERNS_RESEARCHER:
        if re.search(pat, h_lower):
            return step_type

    return "NARRATIVE_STEP"


def infer_entity_transition_warrant(cat1: str, cat2: str, domain_type: str, h1: str, h2: str) -> Tuple[str, str, float]:
    """Infers transition type and deductive warrant between sequential Actor or Location sections."""
    if cat2 == "SYNTHESIS_CATALOG":
        return ("synthesis_catalog", "Catalogs interrelated events, actors, locations, themes, and primary OSINT sources.", 1.0)

    if domain_type == "actor":
        if cat1 == "ACTOR_ANCHOR" and cat2 == "COMMAND_LINEAGE":
            return ("command_lineage", "Traces the actor's historical origins, sub-factions, and command hierarchy.", 1.0)
        if cat1 in ("ACTOR_ANCHOR", "COMMAND_LINEAGE") and cat2 == "STRATEGIC_DOCTRINE":
            return ("strategic_doctrine", "Analyzes the ideological drivers, political economy, and revenue streams sustaining the actor.", 1.0)
        if cat1 == "STRATEGIC_DOCTRINE" and cat2 == "ALLIANCE_NETWORK":
            return ("alliance_network", "Details operational capabilities, weapons systems, coalitions, and external sponsors.", 1.0)
        if cat1 == "ALLIANCE_NETWORK" and cat2 == "EVENT_FOOTPRINT":
            return ("event_footprint", "Documents the actor's chronological conflict footprint and international accountability record.", 1.0)

    if domain_type == "location":
        if cat1 == "LOCATION_ANCHOR" and cat2 == "TERRITORIAL_CONTROL":
            return ("territorial_control", "Details historical and current armed group presence, garrisons, and territorial control shifts.", 1.0)
        if cat1 == "TERRITORIAL_CONTROL" and cat2 == "INFRASTRUCTURE_LOGISTICS":
            return ("infrastructure_logistics", "Maps strategic infrastructure, airports, supply corridors, and natural resources.", 1.0)
        if cat1 == "INFRASTRUCTURE_LOGISTICS" and cat2 == "HUMANITARIAN_STATUS":
            return ("humanitarian_status", "Assesses civilian displacement, IPC food insecurity phase, and health/market access.", 1.0)
        if cat1 == "HUMANITARIAN_STATUS" and cat2 == "EVENT_LOG":
            return ("event_log", "Chronicles major conflict events and battles occurring at this location.", 1.0)

    return ("sequential_progression", f"Progresses sequentially from '{h1}' into '{h2}'.", 0.75)


def extract_and_sync_entity_cot(driver: Driver, database: str = DEFAULT_DATABASE):
    start_time = time.time()
    print("=================================================================")
    print("  Sudan News & OSINT :: Actor & Location CoT Extraction")
    print("  Materializing Micro-CoT Sections & Macro-CoT Agency/Spatial Edges")
    print("=================================================================")

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # -------------------------------------------------------------
        # 1. Micro-CoT: Classify Actor & Location Sections & Progressions
        # -------------------------------------------------------------
        print("\n[1/5] Scanning Intra-Actor & Intra-Location Sections (Micro-CoT)...")
        sec_query = """
        MATCH (e:Document)-[:HAS*1..3]->(s:Section)
        WHERE e:Actor OR e:Location OR e:Entity OR e.type IN ['actor', 'location', 'entity']
        RETURN e.title AS doc_title,
               coalesce(e.type, CASE
                   WHEN e:Location THEN 'location'
                   WHEN e:Actor THEN 'actor'
                   ELSE 'entity'
               END) AS domain_type,
               coalesce(e.subtype, 'armed_group') AS archetype,
               s.uri AS uri,
               coalesce(s.displayName, s.title, s.name, 'Section') AS displayName,
               coalesce(s.content, '') AS content
        """
        sections = session.run(sec_query).data()
        print(f"  → Found {len(sections)} sections across Actor and Location notes.")

        section_updates = []
        for sec in sections:
            step_type = classify_entity_heading(
                sec["displayName"], sec["domain_type"], sec["archetype"], sec["doc_title"]
            )
            section_updates.append({
                "uri": sec["uri"],
                "step_type": step_type,
                "entity_role": step_type,
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (s:Section {uri: item.uri})
            REMOVE s:CognitiveStep
            SET s.step_type = item.step_type,
                s.entity_role = item.entity_role,
                s.cot_classified = true
        """, batch=section_updates)
        print(f"  → Tagged {len(section_updates)} Actor/Location sections with 6-stage step types.")

        pair_query = """
        MATCH (e:Document)-[:HAS*1..3]->(s1:Section)-[:NEXT_SECTION]->(s2:Section)
        WHERE e:Actor OR e:Location OR e:Entity OR e.type IN ['actor', 'location', 'entity']
        RETURN e.title AS doc_title,
               coalesce(e.type, CASE
                   WHEN e:Location THEN 'location'
                   WHEN e:Actor THEN 'actor'
                   ELSE 'entity'
               END) AS domain_type,
               s1.uri AS s1_uri, s1.step_type AS s1_cat, coalesce(s1.displayName, '') AS s1_title,
               s2.uri AS s2_uri, s2.step_type AS s2_cat, coalesce(s2.displayName, '') AS s2_title
        """
        pairs = session.run(pair_query).data()
        transitions = []
        for p in pairs:
            t_type, warrant, conf = infer_entity_transition_warrant(
                p["s1_cat"] or "", p["s2_cat"] or "", p["domain_type"], p["s1_title"], p["s2_title"]
            )
            transitions.append({
                "s1_uri": p["s1_uri"],
                "s2_uri": p["s2_uri"],
                "transition_type": t_type,
                "warrant": warrant,
                "confidence": conf
            })

        session.run("""
            UNWIND $batch AS item
            MATCH (s1:Section {uri: item.s1_uri})
            MATCH (s2:Section {uri: item.s2_uri})
            MERGE (s1)-[r:PROGRESSES_TO]->(s2)
            SET r.transition_type = item.transition_type,
                r.warrant = item.warrant,
                r.confidence = item.confidence,
                r.method = 'actor_location_arc_rule',
                r.updated_at = datetime()
        """, batch=transitions)
        print(f"  → Materialized {len(transitions)} sequential [:PROGRESSES_TO] edges.")

        # -------------------------------------------------------------
        # 2. Macro-CoT: Clean Stale Actor/Location Edges (Idempotency)
        # -------------------------------------------------------------
        print("\n[2/5] Resetting Stale Actor & Location Handshakes...")
        del_res = session.run("""
            MATCH ()-[r:COMMANDED_BY|ALLIED_WITH|SPONSORED_BY|DEFECTED_TO|CONTROLS_TERRITORY|LOCATED_IN|PUBLISHED_BY|ORIGINATES_THEORY|CHAMPIONS_SOLUTION|CRITIQUES_PARADIGM|OPERATIONALIZES|AFFILIATED_WITH|INTELLECTUAL_LINEAGE|AUTHORED_BY]->()
            DELETE r
            RETURN count(r) AS deleted_count
        """).single()
        print(f"  → Cleared {del_res['deleted_count']} previous Actor/Location relationships.")

        # -------------------------------------------------------------
        # 3. Macro-CoT: Materialize Frontmatter & Section-Driven Handshakes
        # -------------------------------------------------------------
        print("\n[3/5] Materializing Frontmatter & Section-Driven Macro-CoT Handshakes...")

        # 3a. [:LOCATED_IN] from Location.parent_location
        loc_parent_res = session.run("""
            MATCH (child:Document)
            WHERE (child:Location OR child.type = 'location') AND child.parent_location IS NOT NULL AND child.parent_location <> ''
            WITH child, replace(replace(child.parent_location, '[[', ''), ']]', '') AS parent_title
            MATCH (parent:Document)
            WHERE (parent:Location OR parent.type = 'location')
              AND (parent.title = parent_title OR parent_title IN coalesce(parent.aliases, []))
            MERGE (child)-[r:LOCATED_IN]->(parent)
            SET r.warrant = child.title + ' is administratively or geographically located in ' + parent.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {loc_parent_res['count']} [:LOCATED_IN] administrative hierarchy links.")

        # 3b. [:COMMANDED_BY] from Actor.leader
        cmd_res = session.run("""
            MATCH (a:Document)
            WHERE (a:Actor OR a.type = 'actor') AND a.leader IS NOT NULL AND a.leader <> ''
            WITH a, replace(replace(a.leader, '[[', ''), ']]', '') AS leader_title
            MATCH (ldr:Document)
            WHERE (ldr:Actor OR ldr.type = 'actor')
              AND (ldr.title = leader_title OR leader_title IN coalesce(ldr.aliases, []))
            MERGE (a)-[r:COMMANDED_BY]->(ldr)
            SET r.warrant = a.title + ' is commanded or led by ' + ldr.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {cmd_res['count']} [:COMMANDED_BY] leadership links.")

        # 3c. [:ALLIED_WITH] from Actor.allies frontmatter & ALLIANCE_NETWORK sections
        allies_fm_res = session.run("""
            MATCH (a1:Document)
            WHERE (a1:Actor OR a1.type = 'actor') AND a1.allies IS NOT NULL
            UNWIND a1.allies AS ally_raw
            WITH a1, replace(replace(ally_raw, '[[', ''), ']]', '') AS ally_title
            MATCH (a2:Document)
            WHERE (a2:Actor OR a2.type = 'actor') AND a1 <> a2
              AND (a2.title = ally_title OR ally_title IN coalesce(a2.aliases, []))
            MERGE (a1)-[r:ALLIED_WITH]->(a2)
            SET r.warrant = a1.title + ' is allied or aligned with ' + a2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()

        allies_sec_res = session.run("""
            MATCH (a1:Document)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(a2:Document)
            WHERE (a1:Actor OR a1.type = 'actor') AND (a2:Actor OR a2.type = 'actor') AND a1 <> a2
              AND s.step_type = 'ALLIANCE_NETWORK'
            WITH a1, a2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (a1)-[r:ALLIED_WITH]->(a2)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = coalesce(r.warrant, a1.title + ' operates in alliance or coordination with ' + a2.title),
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {allies_fm_res['count'] + allies_sec_res['count']} [:ALLIED_WITH] links.")

        # 3d. [:CONTROLS_TERRITORY] from Actor.areas_of_operation and Location TERRITORIAL_CONTROL sections
        ctrl_res = session.run("""
            MATCH (loc:Document)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(act:Document)
            WHERE (loc:Location OR loc.type = 'location')
              AND (act:Actor OR act.type = 'actor')
              AND s.step_type = 'TERRITORIAL_CONTROL'
            WITH act, loc, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (act)-[r:CONTROLS_TERRITORY]->(loc)
            SET r.weight = weight,
                r.source_sections = sections,
                r.control_status = coalesce(loc.current_control, 'contested'),
                r.warrant = act.title + ' maintains armed presence or territorial control in ' + loc.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {ctrl_res['count']} [:CONTROLS_TERRITORY] links.")

        # 3e. [:PUBLISHED_BY] from Source -> Media Actor
        pub_res = session.run("""
            MATCH (src:Source)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(m:Document)
            WHERE m.subtype = 'media_source' OR m:Organization
            WITH src, m, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (src)-[r_rel:PUBLISHED_BY]->(m)
            SET r_rel.weight = weight,
                r_rel.source_sections = sections,
                r_rel.warrant = src.title + ' is published or broadcast by ' + m.title,
                r_rel.updated_at = datetime()
            RETURN count(r_rel) AS count
        """).single()
        print(f"  → Materialized {pub_res['count']} [:PUBLISHED_BY] links.")

        # -------------------------------------------------------------
        # 4. Related Primitives Granular Sub-Bullet Parsing
        # -------------------------------------------------------------
        print("\n[4/5] Parsing Structured Sub-Bullets in 'Related Primitives'...")
        rel_secs = session.run("""
            MATCH (e:Document)-[:HAS*1..3]->(s:Section)
            WHERE (e:Actor OR e:Location OR e:Entity OR e.type IN ['actor', 'location', 'entity'])
              AND (s.displayName IN ['Related Primitives', 'Related Notes', '6. Related Primitives']
                   OR s.step_type = 'SYNTHESIS_CATALOG')
            RETURN e.title AS entity, s.displayName AS sec_name, coalesce(s.content, '') AS content
        """).data()

        bullet_specs = [
            (r"\*\*(?:Command & Leadership|Commanded By)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "COMMANDED_BY", "is commanded by"),
            (r"\*\*(?:Allies & Coalition Partners|Allied With)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "ALLIED_WITH", "is allied with"),
            (r"\*\*(?:Foreign Sponsors|Sponsored By)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "SPONSORED_BY", "is sponsored or supplied by"),
            (r"\*\*(?:Defections|Defected To)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "DEFECTED_TO", "defected to"),
            (r"\*\*(?:Controlled Locations|Areas of Operation|Territorial Control)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "CONTROLS_TERRITORY", "operates in or controls"),
            (r"\*\*(?:Parent Location|Located In)\*\*:(.*?)(?=\n\s*-\s*\*\*|\Z)", "LOCATED_IN", "is located in"),
        ]

        bullet_counts = {spec[1]: 0 for spec in bullet_specs}

        for r_sec in rel_secs:
            e_title = r_sec["entity"]
            c_text = r_sec["content"]

            for pattern, rel_type, warrant_verb in bullet_specs:
                matches = re.findall(pattern, c_text, re.DOTALL | re.IGNORECASE)
                for chunk in matches:
                    targets = re.findall(r"\[\[([^\]\|\\]+)(?:\\?\|[^\]]+)?\]\]", chunk)
                    for t in targets:
                        t_clean = t.strip().split("/")[-1]
                        session.run(f"""
                            MATCH (e:Document {{title: $e_title}})
                            MATCH (dst:Document {{title: $t_clean}})
                            MERGE (e)-[r:{rel_type}]->(dst)
                            SET r.weight = coalesce(r.weight, 0) + 1,
                                r.warrant = e.title + ' {warrant_verb} ' + dst.title,
                                r.updated_at = datetime()
                        """, e_title=e_title, t_clean=t_clean)
                        bullet_counts[rel_type] += 1

        for r_type, cnt in bullet_counts.items():
            if cnt > 0:
                print(f"    * [:{r_type}]: +{cnt}")

        # -------------------------------------------------------------
        # 5. Graph Verification & Summary Telemetry
        # -------------------------------------------------------------
        print("\n[5/5] Computing Actor & Location Telemetry...")
        summary = session.run("""
            MATCH (e:Document)-[r]->(target)
            WHERE type(r) IN ['COMMANDED_BY', 'ALLIED_WITH', 'SPONSORED_BY', 'DEFECTED_TO',
                              'CONTROLS_TERRITORY', 'LOCATED_IN', 'PUBLISHED_BY']
            RETURN type(r) AS rel_type, count(r) AS count, count(DISTINCT e) AS active_nodes
            ORDER BY count DESC
        """).data()

        print("\n  ================ Active Actor & Location Predicates ================")
        print(f"  {'Relationship Predicate':<26} | {'Total Edges':<12} | {'Active Nodes':<15}")
        print("  " + "-" * 60)
        total_macro = 0
        for row in summary:
            print(f"  [:{row['rel_type']:<24}] | {row['count']:<12} | {row['active_nodes']:<15}")
            total_macro += row["count"]
        print("  " + "-" * 60)
        print(f"  {'Total Materialized Edges':<26} | {total_macro:<12} |")
        print("  ====================================================================")

    elapsed = time.time() - start_time
    print(f"\n[✓] Actor & Location CoT Extraction Complete in {elapsed:.2f}s!")


def main():
    parser = argparse.ArgumentParser(description="Extract Actor & Location CoT Arcs into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        extract_and_sync_entity_cot(driver, database=args.database)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
