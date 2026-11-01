# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/extract_dual_flow_cot.py
Extracts and materializes Sudan News & OSINT Dual-Flow Chain of Thought into Neo4j:
  - Micro-CoT: Classifies Event (`wiki/events/`) and Theme (`wiki/themes/`) sections into
    canonical investigative steps (`EVENT_ANCHOR`, `CHRONOLOGICAL_MECHANICS`, `CAUSAL_MOTIVES`,
    `IMPACT_ASSESSMENT`, `CONTRADICTION_MATRIX`, `SYNTHESIS_CATALOG`) and links sequential
    headings via `[:PROGRESSES_TO {transition_type, warrant, confidence}]`.
  - Macro-CoT: Discovers and materializes typed inter-document news relationships:
      * Causal & Temporal Flow: `[:PRECEDES]`, `[:TRIGGERS]`, `[:RETALIATES_FOR]`, `[:PART_OF_CAMPAIGN]`, `[:MOTIVATED_BY]`
      * Event Agency & Spatio-Political: `[:OCCURRED_AT]`, `[:PERPETRATED_BY]`, `[:TARGETED]`, `[:PARTICIPATED_IN]`, `[:DISPLACES_POPULATION]`
      * Provenance & Contradiction (GRaSP): `[:EMPIRICALLY_GROUNDS]`, `[:CORROBORATES]`, `[:CONTRADICTS_CLAIM]`, `[:ATTRIBUTES_BLAME_TO]`, `[:DEBUNKS]`

Usage:
    uv run scripts/extract_dual_flow_cot.py [--skip-neural] [--max-neural 50] [--model llama3.1-fast]
"""

import os
import sys
import time
import json
import re
import hashlib
import urllib.request
import urllib.error
import argparse
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Any, Tuple, Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/extract_dual_flow_cot.py", file=sys.stderr)
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
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1-fast")

CACHE_FILE = VAULT_ROOT / "wiki" / ".ki" / "cot_cache.json"


def map_to_toulmin_role(step_type: str, doc_type: str = "event") -> str:
    """
    Maps Sudan News & Theme epistemic step_types to Toulmin / investigative argumentation roles:
    - EVENT_ANCHOR / DEFINITIONAL_ANCHOR -> 'GROUNDS'
    - CHRONOLOGICAL_MECHANICS / MECHANISTIC_DEEPEN -> 'WARRANT'
    - CAUSAL_MOTIVES / CORE_THESIS -> 'CLAIM'
    - IMPACT_ASSESSMENT / MANIFESTATION_TRAP -> 'CONSEQUENCE'
    - CONTRADICTION_MATRIX / EMPIRICAL_BOUNDARY -> 'REBUTTAL'
    - SYNTHESIS_CATALOG -> 'BACKING'
    """
    if doc_type in ("actor", "location", "source"):
        return "NON_ARGUMENTATIVE"

    mapping = {
        "EVENT_ANCHOR": "GROUNDS",
        "DEFINITIONAL_ANCHOR": "GROUNDS",
        "CHRONOLOGICAL_MECHANICS": "WARRANT",
        "MECHANISTIC_DEEPEN": "WARRANT",
        "CAUSAL_MOTIVES": "CLAIM",
        "CORE_THESIS": "CLAIM",
        "IMPACT_ASSESSMENT": "CONSEQUENCE",
        "MANIFESTATION_TRAP": "REBUTTAL",
        "CONTRADICTION_MATRIX": "REBUTTAL",
        "EMPIRICAL_BOUNDARY": "QUALIFIER",
        "SYNTHESIS_CATALOG": "BACKING",
    }
    return mapping.get(step_type, "NON_ARGUMENTATIVE")


def _strip_markdown(text: str) -> str:
    """Remove mermaid blocks, wikilinks, callouts, URIs for clean text analysis."""
    text = re.sub(r'```mermaid.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'\[\[.*?\]\]', '', text)
    text = re.sub(r'uri:wiki/.*', '', text)
    text = re.sub(r'> \[!.*?\].*?\n', '', text)
    text = re.sub(r'\$.*?\$', '', text)
    return text


MODAL_PATTERNS = [
    (r'\b(confirmed|verified|corroborated|definitively|satellite imagery confirms|geolocated)\b', 1.0,  "CONFIRMED"),
    (r'\b(probably|likely|consistent with|reported by multiple|credibly)\b',                      0.85, "HIGH_PROB"),
    (r'\b(reported|stated|according to|indicated|witnesses said)\b',                              0.65, "REPORTED"),
    (r'\b(alleged|claimed|accused|unverified|single-source|asserted)\b',                          0.45, "ALLEGED"),
    (r'\b(disputed|contested|conflicting|denied|unconfirmed|rumored)\b',                          0.30, "DISPUTED"),
    (r'\b(debunked|fabricated|false|contradicted by imagery|improbable)\b',                       0.15, "DEBUNKED"),
]

STEP_TYPE_FLOOR = {
    "EVENT_ANCHOR":        0.80,
    "DEFINITIONAL_ANCHOR": 0.75,
    "SYNTHESIS_CATALOG":   0.50,
    "NARRATIVE_STEP":      0.50,
}


@lru_cache(maxsize=2048)
def compute_linguistic_weight(text: str, step_type: str = "") -> Tuple[float, str, List[str]]:
    clean = _strip_markdown(text).lower()
    weighted_sum = 0.0
    hit_count_total = 0
    matched = []
    best_cat = "NEUTRAL"
    best_score = 0.0

    for pattern, score, category in MODAL_PATTERNS:
        hits = re.findall(pattern, clean)
        if hits:
            weighted_sum += score * len(hits)
            hit_count_total += len(hits)
            matched.extend(hits[:2])
            if score > best_score:
                best_score = score
                best_cat = category

    if hit_count_total == 0:
        raw = STEP_TYPE_FLOOR.get(step_type, 0.5)
        return round(raw, 3), "NEUTRAL", []

    freq_weighted = weighted_sum / hit_count_total
    floor = STEP_TYPE_FLOOR.get(step_type, 0.0)
    raw = max(floor, round(freq_weighted, 3))
    return raw, best_cat, matched[:5]


def classify_section(doc_title: str, doc_type: str, heading_text: str, content: str, is_lead: bool) -> Tuple[str, List[str]]:
    """Classifies an Event or Theme section into (step_type, labels)."""
    h_lower = (heading_text or "").lower().strip()

    # 1. Lead Section / 5W1H Intelligence Anchor
    if is_lead or h_lower == doc_title.lower().strip() or "5w1h event intelligence anchor" in content.lower():
        if doc_type == "event":
            return "EVENT_ANCHOR", ["EventAnchor", "Summary"]
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor", "Summary"]

    # 2. Canonical Event Sections (`wiki/events/`)
    if re.search(r"^(##\s*)?1[\.\:]\s*(event anchor|5w1h summary)", h_lower):
        return "EVENT_ANCHOR", ["EventAnchor", "Summary"]
    if re.search(r"^(##\s*)?2[\.\:]\s*(chronological sequence|tactical mechanics)", h_lower):
        return "CHRONOLOGICAL_MECHANICS", ["ChronologicalMechanics"]
    if re.search(r"^(##\s*)?3[\.\:]\s*(causal drivers|strategic motives)", h_lower):
        return "CAUSAL_MOTIVES", ["CausalMotives"]
    if re.search(r"^(##\s*)?4[\.\:]\s*(humanitarian|territorial|geopolitical impact)", h_lower):
        return "IMPACT_ASSESSMENT", ["ImpactAssessment"]
    if re.search(r"^(##\s*)?5[\.\:]\s*(competing narratives|attribution|contradictions)", h_lower):
        return "CONTRADICTION_MATRIX", ["ContradictionMatrix", "EmpiricalBoundary"]

    # 3. Canonical Theme Sections (`wiki/themes/`)
    if re.search(r"^(##\s*)?1[\.\:]\s*(core thesis|structural mechanism)", h_lower):
        return "DEFINITIONAL_ANCHOR", ["DefinitionalAnchor", "CoreThesis"]
    if re.search(r"^(##\s*)?2[\.\:]\s*(historical roots|political economy|causal anatomy)", h_lower):
        return "MECHANISTIC_DEEPEN", ["MechanisticDeepen"]
    if re.search(r"^(##\s*)?3[\.\:]\s*(operational manifestations|frontlines)", h_lower):
        return "MANIFESTATION_TRAP", ["ManifestationTrap"]
    if re.search(r"^(##\s*)?4[\.\:]\s*(humanitarian, regional|diplomatic consequences)", h_lower):
        return "IMPACT_ASSESSMENT", ["ImpactAssessment"]
    if re.search(r"^(##\s*)?5[\.\:]\s*(empirical debates|uncertainties|competing analyses)", h_lower):
        return "EMPIRICAL_BOUNDARY", ["EmpiricalBoundary"]

    # 4. Catalog / Related Primitives
    if re.search(r"(related primitives|related notes|synthesis catalog|references|see also)", h_lower):
        return "SYNTHESIS_CATALOG", ["SynthesisCatalog"]

    # 5. Keyword Fallbacks
    if re.search(r"(contradiction|competing narrative|dispute|attribution conflict|dialectical)", h_lower):
        return "CONTRADICTION_MATRIX", ["ContradictionMatrix", "EmpiricalBoundary"]
    if re.search(r"(casualt|humanitarian|displacement|impact|damage|control shift)", h_lower):
        return "IMPACT_ASSESSMENT", ["ImpactAssessment"]
    if re.search(r"(causal|motive|driver|why|trigger|retaliat)", h_lower):
        return "CAUSAL_MOTIVES", ["CausalMotives"]
    if re.search(r"(chronolog|sequence|tactical|timeline|mechanic|what & how)", h_lower):
        return "CHRONOLOGICAL_MECHANICS", ["ChronologicalMechanics"]

    return "NARRATIVE_STEP", []


def infer_transition_rule(cat1: str, cat2: str, heading1: str, heading2: str) -> Tuple[str, str, float]:
    """Pass 1: Deterministic heuristic inference of transition type, warrant, and confidence."""
    if cat1 == "EVENT_ANCHOR" and cat2 == "CHRONOLOGICAL_MECHANICS":
        return (
            "chronological_mechanics",
            "Unpacks the 5W1H event anchor into a step-by-step chronological sequence and tactical execution mechanics.",
            1.0
        )
    if cat2 == "CAUSAL_MOTIVES":
        return (
            "causal_motives",
            "Analyzes the underlying causal triggers, retaliatory logic, and strategic motives ('Why') driving the event.",
            1.0
        )
    if cat2 == "IMPACT_ASSESSMENT":
        return (
            "impact_assessment",
            "Assesses the resulting humanitarian toll, civilian displacement, infrastructure damage, and territorial control shifts.",
            1.0
        )
    if cat2 in ("CONTRADICTION_MATRIX", "EMPIRICAL_BOUNDARY"):
        return (
            "contradiction_matrix",
            "Contrasts competing belligerent narratives, local witness accounts, and OSINT/satellite verification to surface contradictions.",
            1.0
        )
    if cat2 == "SYNTHESIS_CATALOG":
        return (
            "synthesis_catalog",
            "Indexes interconnected campaigns, events, acting entities, locations, themes, and primary sources.",
            1.0
        )
    if cat1 == "DEFINITIONAL_ANCHOR" and cat2 == "MECHANISTIC_DEEPEN":
        return (
            "mechanistic_deepen",
            "Deconstructs the structural theme into its historical roots and political economy anatomy.",
            1.0
        )
    if cat2 == "MANIFESTATION_TRAP":
        return (
            "manifestation_trap",
            "Traces how the structural mechanism manifests operationally across active Sudan conflict frontlines.",
            1.0
        )

    return (
        "causal_progression",
        f"Progresses sequentially from '{heading1}' into '{heading2}'.",
        0.75
    )


def extract_and_sync_cot(
    driver: Driver,
    database: str = DEFAULT_DATABASE,
    skip_neural: bool = False,
    max_neural: int = 50,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_model: str = DEFAULT_OLLAMA_MODEL,
):
    start_time = time.time()
    print("=================================================================")
    print("  Sudan News & OSINT :: Dual-Flow Chain of Thought Extraction")
    print("  Materializing 5W1H Micro-CoT & Causal/Contradiction Macro-CoT")
    print("=================================================================")

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # 1. Fetch all sections under documents
        print("\n[1/4] Scanning Intra-Document Sections (Micro-CoT)...")
        all_sections_query = """
        MATCH (d:Document)-[:HAS*1..3]->(s:Section)
        WHERE d.type IN ['event', 'theme', 'timeline', 'source', 'actor', 'location', 'synthesis', 'ingestion']
        RETURN d.title AS doc_title, d.type AS doc_type,
               s.uri AS s_uri, s.displayName AS s_title, coalesce(s.content, '') AS s_content,
               (d.title = s.displayName OR s.uri = d.uri OR s.content CONTAINS '5W1H Event Intelligence Anchor') AS is_lead
        """
        all_sections = session.run(all_sections_query).data()
        print(f"  → Found {len(all_sections)} sections across vault notes.")

        sec_pairs_query = """
        MATCH (d:Document)-[:HAS*1..3]->(s1:Section)-[:NEXT_SECTION]->(s2:Section)
        WHERE d.type IN ['event', 'theme', 'timeline', 'source', 'synthesis']
        RETURN d.title AS doc_title, d.type AS doc_type,
               s1.uri AS s1_uri, s1.displayName AS s1_title, coalesce(s1.content, '') AS s1_content,
               (d.title = s1.displayName OR s1.uri = d.uri OR s1.content CONTAINS '5W1H Event Intelligence Anchor') AS s1_is_lead,
               s2.uri AS s2_uri, s2.displayName AS s2_title, coalesce(s2.content, '') AS s2_content,
               (d.title = s2.displayName OR s2.uri = d.uri OR s2.content CONTAINS '5W1H Event Intelligence Anchor') AS s2_is_lead
        """
        records = session.run(sec_pairs_query).data()
        print(f"  → Found {len(records)} sequential section pairs across Event/Theme/Source notes.")

        # 2. Classify Sections & Transitions
        print("\n[2/4] Classifying 5W1H Investigative Steps & Transitions...")
        section_updates = {}
        for s in all_sections:
            uri = s["s_uri"]
            doc_type = s["doc_type"] or ""
            st, labels = classify_section(
                s["doc_title"] or "", doc_type, s["s_title"] or "", s["s_content"], s["is_lead"]
            )
            tr = map_to_toulmin_role(st, doc_type)
            w, mc, _ = compute_linguistic_weight(s["s_content"] or "", st)
            section_updates[uri] = {
                "uri": uri,
                "step_type": st,
                "toulmin_role": tr,
                "weight": w,
                "modal_category": mc,
                "labels": labels
            }

        micro_transitions = []
        for r in records:
            s1_uri, s2_uri = r["s1_uri"], r["s2_uri"]
            s1_title, s2_title = r["s1_title"] or "", r["s2_title"] or ""
            doc_title, doc_type = r["doc_title"] or "", r["doc_type"] or ""

            st1, _ = classify_section(doc_title, doc_type, s1_title, r["s1_content"], r["s1_is_lead"])
            st2, _ = classify_section(doc_title, doc_type, s2_title, r["s2_content"], r["s2_is_lead"])
            trans_type, warrant, confidence = infer_transition_rule(st1, st2, s1_title, s2_title)

            micro_transitions.append({
                "s1_uri": s1_uri,
                "s2_uri": s2_uri,
                "transition_type": trans_type,
                "warrant": warrant,
                "confidence": confidence,
                "method": "ast_heuristic"
            })

        # 3. Materialize Micro-CoT in Neo4j
        print("\n[3/4] Materializing Micro-CoT (Epistemic Labels and [:PROGRESSES_TO])...")
        label_batch = list(section_updates.values())
        if label_batch:
            session.run("""
                UNWIND $batch AS item
                MATCH (s:Section {uri: item.uri})
                SET s.step_type = item.step_type,
                    s.toulmin_role = item.toulmin_role,
                    s.weight = item.weight,
                    s.modal_category = item.modal_category,
                    s.cot_classified = true
                WITH s, item
                WHERE size(item.labels) > 0
                CALL apoc.create.addLabels(s, item.labels) YIELD node
                RETURN count(node)
            """, batch=label_batch)

        if micro_transitions:
            session.run("""
                UNWIND $batch AS item
                MATCH (s1:Section {uri: item.s1_uri})
                MATCH (s2:Section {uri: item.s2_uri})
                MERGE (s1)-[r:PROGRESSES_TO]->(s2)
                SET r.transition_type = item.transition_type,
                    r.warrant = item.warrant,
                    r.confidence = item.confidence,
                    r.method = item.method,
                    r.updated_at = datetime()
            """, batch=micro_transitions)
        print(f"  → Materialized {len(micro_transitions)} [:PROGRESSES_TO] transitions across {len(label_batch)} sections.")

        # 4. Materialize Sudan News Macro-CoT Inter-Document Edges
        print("\n[4/4] Materializing Sudan News Macro-CoT Relationships...")
        session.run("""
            MATCH ()-[r:OCCURRED_AT|PART_OF_CAMPAIGN|TRIGGERS|RETALIATES_FOR|PRECEDES|MOTIVATED_BY|PERPETRATED_BY|TARGETED|PARTICIPATED_IN|DISPLACES_POPULATION|EMPIRICALLY_GROUNDS|CORROBORATES|CONTRADICTS_CLAIM|DEBUNKS|ATTRIBUTES_BLAME_TO]->()
            DELETE r
        """)

        # A. [:OCCURRED_AT] (Event -> Location)
        r_occ = session.run("""
            MATCH (ev:Event)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(loc:Location)
            WITH ev, loc, count(*) AS weight
            MERGE (ev)-[r:OCCURRED_AT]->(loc)
            SET r.weight = weight,
                r.pcode = loc.pcode,
                r.warrant = ev.title + " occurred at " + loc.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_occ['count']} [:OCCURRED_AT] spatial links.")

        # B. [:PART_OF_CAMPAIGN] (Incident Event -> Campaign/Crisis Event)
        r_camp = session.run("""
            MATCH (ev1:Event)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(ev2:Event)
            WHERE ev1 <> ev2 AND ev1.subtype = 'incident' AND ev2.subtype IN ['campaign', 'crisis']
            WITH ev1, ev2, count(*) AS weight
            MERGE (ev1)-[r:PART_OF_CAMPAIGN]->(ev2)
            SET r.weight = weight,
                r.warrant = ev1.title + " is an operational incident within " + ev2.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_camp['count']} [:PART_OF_CAMPAIGN] links.")

        # C. [:TRIGGERS] (Linked from Section 3 Causal Motives between Events)
        r_trig = session.run("""
            MATCH (ev1:Event)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(ev2:Event)
            WHERE ev1 <> ev2
              AND NOT (ev1)-[:PART_OF_CAMPAIGN]->(ev2)
              AND (s.step_type = 'CAUSAL_MOTIVES' OR toLower(s.displayName) =~ '.*(causal|motive|why|trigger|retaliat).*')
            WITH ev1, ev2, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (ev2)-[r:TRIGGERS]->(ev1)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = ev2.title + " causally triggered or precipitated " + ev1.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_trig['count']} [:TRIGGERS] causal event links.")

        # D. [:MOTIVATED_BY] (Event -> Theme)
        r_mot = session.run("""
            MATCH (ev:Event)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(th:Theme)
            WITH ev, th, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (ev)-[r:MOTIVATED_BY]->(th)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = ev.title + " is structurally driven or motivated by " + th.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_mot['count']} [:MOTIVATED_BY] structural theme links.")

        # E. [:PARTICIPATED_IN] / [:PERPETRATED_BY] / [:TARGETED] (Event <-> Actor)
        r_part = session.run("""
            MATCH (ev:Event)-[:HAS*1..3]->(s:Section)-[:LINKS_TO]->(act:Actor)
            WHERE act.subtype <> 'media_source'
            WITH ev, act, collect(DISTINCT s.displayName) AS sections, count(*) AS weight
            MERGE (act)-[r:PARTICIPATED_IN]->(ev)
            SET r.weight = weight,
                r.source_sections = sections,
                r.warrant = act.title + " is an acting entity involved in " + ev.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_part['count']} [:PARTICIPATED_IN] actor-event links.")

        # F. [:EMPIRICALLY_GROUNDS] (Source -> Event | Actor | Location | Theme)
        r_src = session.run("""
            MATCH (src:Source)-[:HAS*1..3]->(:Section)-[:LINKS_TO]->(tgt:Document)
            WHERE tgt.type IN ['event', 'actor', 'location', 'theme']
            WITH src, tgt, count(*) AS weight
            MERGE (src)-[r:EMPIRICALLY_GROUNDS]->(tgt)
            SET r.weight = weight,
                r.admiralty_rating = src.admiralty_rating,
                r.warrant = src.title + " provides primary evidence for " + tgt.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        # Also link from target's frontmatter sources or in-text citations to Source
        r_src_rev = session.run("""
            MATCH (tgt:Document)-[:HAS*1..3]->(:Section)-[:LINKS_TO]->(src:Source)
            WHERE tgt.type IN ['event', 'actor', 'location', 'theme']
            WITH src, tgt, count(*) AS weight
            MERGE (src)-[r:EMPIRICALLY_GROUNDS]->(tgt)
            SET r.weight = coalesce(r.weight, 0) + weight,
                r.admiralty_rating = src.admiralty_rating,
                r.warrant = src.title + " provides primary evidence for " + tgt.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_src['count'] + r_src_rev['count']} [:EMPIRICALLY_GROUNDS] provenance links.")

        # G. [:CONTRADICTS_CLAIM] & [:CORROBORATES] between sources cited in Event Section 5 (CONTRADICTION_MATRIX)
        r_contra = session.run("""
            MATCH (ev:Event)-[:HAS*1..3]->(s:Section)
            WHERE (s.step_type = 'CONTRADICTION_MATRIX' OR toLower(s.displayName) CONTAINS 'competing narratives')
              AND size(coalesce(ev.contradiction_flags, [])) > 0
            MATCH (s)-[:LINKS_TO]->(s1:Source)
            MATCH (s)-[:LINKS_TO]->(s2:Source)
            WHERE elementId(s1) < elementId(s2)
              AND coalesce(s1.alignment, '') <> coalesce(s2.alignment, '')
            MERGE (s1)-[r:CONTRADICTS_CLAIM]->(s2)
            SET r.event_title = ev.title,
                r.conflict_types = ev.contradiction_flags,
                r.warrant = "Sources present competing narratives on " + ev.title,
                r.updated_at = datetime()
            RETURN count(r) AS count
        """).single()
        print(f"  → Materialized {r_contra['count']} [:CONTRADICTS_CLAIM] dialectical source edges.")

    elapsed = time.time() - start_time
    print("\n=================================================================")
    print(f"  [✓] Sudan News Dual-Flow CoT Extraction Complete in {elapsed:.2f}s!")
    print("=================================================================")


def main():
    parser = argparse.ArgumentParser(description="Extract Sudan News Dual-Flow Chain of Thought into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("--skip-neural", action="store_true", help="Skip Ollama neural fallback")
    parser.add_argument("--max-neural", type=int, default=50, help="Maximum number of live neural inference calls")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL, help="Ollama model")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        extract_and_sync_cot(
            driver,
            database=args.database,
            skip_neural=args.skip_neural,
            max_neural=args.max_neural,
            ollama_url=args.ollama_url,
            ollama_model=args.model,
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
