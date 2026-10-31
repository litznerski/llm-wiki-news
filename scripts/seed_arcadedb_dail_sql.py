#!/usr/bin/env python3
"""
scripts/seed_arcadedb_dail_sql.py
Seeds verified Question-Query exemplars into ArcadeDB for DAIL-SQL in-context retrieval.
Derives 12 verified sample queries from raw/documentation/arcadedb_sample_queries_and_verification_guide.md.
"""

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List

VAULT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(VAULT_ROOT))

from scripts.arcadedb_client import ArcadeDBClient

# 12 Verified Exemplars from raw/documentation/arcadedb_sample_queries_and_verification_guide.md
EXEMPLARS: List[Dict[str, Any]] = [
    {
        "id": "demo_01",
        "question": "Show the top 3 ranked concepts by authority",
        "query": (
            "MATCH (c:Concept)\n"
            "WHERE c.pagerank IS NOT NULL\n"
            "RETURN c.title AS title, c.pagerank AS pagerank, c.community AS community, c.reliability_score AS reliability\n"
            "ORDER BY c.pagerank DESC\n"
            "LIMIT 3;"
        ),
        "dialect": "cypher",
        "intent": "pagerank_ranking",
        "keywords": ["top", "ranked", "concepts", "pagerank", "authority", "centrality"],
        "complexity": "simple",
    },
    {
        "id": "demo_02",
        "question": "Show the top 3 ranked entities",
        "query": (
            "MATCH (e:Entity)\n"
            "WHERE e.pagerank IS NOT NULL\n"
            "RETURN e.title AS title, e.subtype AS subtype, e.pagerank AS pagerank, e.community AS community\n"
            "ORDER BY e.pagerank DESC\n"
            "LIMIT 3;"
        ),
        "dialect": "cypher",
        "intent": "entity_ranking",
        "keywords": ["top", "ranked", "entities", "pagerank", "researcher", "organization", "software"],
        "complexity": "simple",
    },
    {
        "id": "demo_03",
        "question": "Show all hub concepts and entities in Community 68",
        "query": (
            "MATCH (n)\n"
            "WHERE n.community = 68 AND (n:Concept OR n:Entity)\n"
            "RETURN coalesce(n.subtype, 'concept') AS node_type, n.title AS title, n.pagerank AS pagerank\n"
            "ORDER BY n.pagerank DESC\n"
            "LIMIT 10;"
        ),
        "dialect": "cypher",
        "intent": "community_cluster",
        "keywords": ["community", "cluster", "68", "hub", "concepts", "entities", "louvain"],
        "complexity": "simple",
    },
    {
        "id": "demo_04",
        "question": "Find the shortest path between AI Learning Paradox and Cognitive Surrender",
        "query": (
            "MATCH (start:Concept {title: 'AI Learning Paradox'}), (target:Concept {title: 'Cognitive Surrender'})\n"
            "MATCH p = shortestPath((start)-[*..5]-(target))\n"
            "RETURN [n IN nodes(p) | n.title] AS path, [r IN relationships(p) | type(r)] AS relationships, length(p) AS hops;"
        ),
        "dialect": "cypher",
        "intent": "shortest_path",
        "keywords": ["shortest", "path", "ai learning paradox", "cognitive surrender", "hops", "trajectory"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_05",
        "question": "Show 2-hop bridging concepts between AI Learning Paradox and Cognitive Surrender",
        "query": (
            "MATCH (start:Concept {title: 'AI Learning Paradox'})-[r1]->(mid:Concept)-[r2]->(target:Concept {title: 'Cognitive Surrender'})\n"
            "RETURN start.title AS start_concept, type(r1) AS rel_out, mid.title AS bridging_concept, type(r2) AS rel_in, target.title AS target_concept\n"
            "LIMIT 5;"
        ),
        "dialect": "cypher",
        "intent": "bridging_paths",
        "keywords": ["bridging", "intermediary", "2-hop", "ai learning paradox", "cognitive surrender", "path"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_06",
        "question": "What solutions or mitigations remedy Cognitive Surrender?",
        "query": (
            "MATCH (c:Concept {title: 'Cognitive Surrender'})-[r:REMEDIES_DILEMMA]->(s:Concept)\n"
            "RETURN s.title AS solution_title, s.pagerank AS pagerank, s.community AS community\n"
            "ORDER BY pagerank DESC;"
        ),
        "dialect": "cypher",
        "intent": "cot_remedy_out",
        "keywords": ["remedy", "solutions", "mitigations", "cognitive surrender", "remedies_dilemma", "safeguards"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_07",
        "question": "What concepts independently target and remedy Cognitive Surrender?",
        "query": (
            "MATCH (remedy:Concept)-[:REMEDIES_DILEMMA]->(target:Concept {title: 'Cognitive Surrender'})\n"
            "RETURN remedy.title AS remedy_title, remedy.pagerank AS pagerank\n"
            "ORDER BY pagerank DESC;"
        ),
        "dialect": "cypher",
        "intent": "cot_remedy_in",
        "keywords": ["incoming", "mitigate", "remedy", "cognitive surrender", "target", "countermeasures"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_08",
        "question": "Find the 5 most similar sections to the Core Thesis using vector search",
        "query": (
            "SELECT title, path, step_type,\n"
            "       vectorNeighbors('Section[embedding]', (SELECT embedding FROM Section WHERE title = '1. Core Thesis & Definitional Anchor' LIMIT 1)[0].embedding, 5) AS distance\n"
            "FROM Section\n"
            "ORDER BY distance ASC\n"
            "LIMIT 5;"
        ),
        "dialect": "sql",
        "intent": "vector_knn",
        "keywords": ["vector", "knn", "similar", "sections", "distance", "embedding", "vectorneighbors"],
        "complexity": "simple",
    },
    {
        "id": "demo_09",
        "question": "Perform a hybrid search finding similar sections and their parent note",
        "query": (
            "SELECT title, path, step_type,\n"
            "       in('HAS_SECTION').title AS parent_document\n"
            "FROM Section\n"
            "ORDER BY vectorNeighbors('Section[embedding]', (SELECT embedding FROM Section WHERE title = '2. Causal Anatomy & Underlying Mechanics' LIMIT 1)[0].embedding, 3) ASC\n"
            "LIMIT 3;"
        ),
        "dialect": "sql",
        "intent": "hybrid_search",
        "keywords": ["hybrid", "search", "vectorneighbors", "parent", "has_section", "out", "in"],
        "complexity": "hybrid",
    },
    {
        "id": "demo_010",
        "question": "Show the micro-reasoning steps inside Cognitive Surrender",
        "query": (
            "MATCH (s1:Section)-[r:PROGRESSES_TO]->(s2:Section)\n"
            "WHERE s1.path CONTAINS 'Cognitive Surrender.md'\n"
            "RETURN s1.step_type AS from_step, s1.title AS from_section, r.transition_type AS reasoning_type, s2.step_type AS to_step, s2.title AS to_section\n"
            "LIMIT 5;"
        ),
        "dialect": "cypher",
        "intent": "cot_progression",
        "keywords": ["micro-cot", "reasoning", "steps", "progresses_to", "cognitive surrender", "progression"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_011",
        "question": "Resolve aliases for Cognitive Offloading and PCF",
        "query": (
            "SELECT alias, canonical_title\n"
            "FROM AliasLookup\n"
            "WHERE alias IN ['Cognitive Offloading', 'PCF'];"
        ),
        "dialect": "sql",
        "intent": "alias_resolution",
        "keywords": ["alias", "lookup", "cognitive offloading", "pcf", "canonical", "aliaslookup"],
        "complexity": "simple",
    },
    {
        "id": "demo_012",
        "question": "What are the active agency relationships for Knowledge Lab?",
        "query": (
            "MATCH (e:Entity {title: 'Knowledge Lab'})-[r]->(target)\n"
            "RETURN type(r) AS agency_relation, labels(target)[0] AS target_type, target.title AS target_primitive\n"
            "ORDER BY agency_relation, target_primitive;"
        ),
        "dialect": "cypher",
        "intent": "entity_agency",
        "keywords": ["agency", "Knowledge Lab", "relationships", "originates_theory", "operationalizes", "champions_solution"],
        "complexity": "multi_hop",
    },
    # Toulmin Traversal & Epistemic Weight Exemplars
    {
        "id": "demo_013",
        "question": "Why does Productive Cognitive Friction work?",
        "query": (
            "MATCH (c:Concept {title: 'Productive Cognitive Friction'})-[e:HAS_WARRANT]->(w:Section)\n"
            "WHERE e.weight IS NOT NULL\n"
            "RETURN w.title AS warrant_title, e.weight AS epistemic_weight, w.modal_category AS certainty, substring(w.content, 0, 200) AS content_preview\n"
            "ORDER BY e.weight DESC;"
        ),
        "dialect": "cypher",
        "intent": "toulmin_warrant",
        "keywords": ["why does", "warrant", "causal anatomy", "mechanics", "has_warrant", "how does it work", "weight"],
        "complexity": "simple",
    },
    {
        "id": "demo_014",
        "question": "What are the failure modes of Productive Cognitive Friction?",
        "query": (
            "MATCH (c:Concept {title: 'Productive Cognitive Friction'})-[e:HAS_REBUTTAL]->(reb:Section)\n"
            "WHERE e.signed_weight IS NOT NULL\n"
            "RETURN reb.title AS rebuttal_title, e.signed_weight AS attack_weight, reb.modal_category AS modal_category, substring(reb.content, 0, 200) AS content_preview\n"
            "ORDER BY e.signed_weight ASC;"
        ),
        "dialect": "cypher",
        "intent": "toulmin_rebuttal",
        "keywords": ["failure modes", "rebuttal", "traps", "pathologies", "has_rebuttal", "what breaks", "attack weight"],
        "complexity": "simple",
    },
    {
        "id": "demo_015",
        "question": "What prescriptive solutions or counter-architectures solve Cognitive Surrender?",
        "query": (
            "MATCH (c:Concept {title: 'Cognitive Surrender'})-[e:HAS_SOLUTION]->(s:Section)\n"
            "WHERE e.weight IS NOT NULL\n"
            "RETURN s.title AS solution_title, e.weight AS solution_weight, s.modal_category AS certainty, substring(s.content, 0, 200) AS content_preview\n"
            "ORDER BY e.weight DESC;"
        ),
        "dialect": "cypher",
        "intent": "toulmin_solution",
        "keywords": ["solution warrant", "prescriptive mitigation", "counter-architecture", "has_solution", "fix", "weight"],
        "complexity": "simple",
    },
    {
        "id": "demo_016",
        "question": "What are the empirical grounds and definitional anchors for AI Learning Paradox?",
        "query": (
            "MATCH (c:Concept {title: 'AI Learning Paradox'})-[e:HAS_GROUNDS]->(g:Section)\n"
            "WHERE e.weight IS NOT NULL\n"
            "RETURN g.title AS grounds_title, e.weight AS grounds_weight, g.modal_category AS certainty, substring(g.content, 0, 200) AS content_preview\n"
            "ORDER BY e.weight DESC;"
        ),
        "dialect": "cypher",
        "intent": "toulmin_grounds",
        "keywords": ["definitional anchor", "grounds", "data anchor", "has_grounds", "evidence", "weight"],
        "complexity": "simple",
    },
    {
        "id": "demo_017",
        "question": "Retrieve apprentice context for Productive Cognitive Friction in teachable agent mode without answers",
        "query": (
            "MATCH (c:Concept {title: 'Productive Cognitive Friction'})-[r:HAS_GROUNDS|HAS_REBUTTAL]->(s:Section)\n"
            "RETURN type(r) AS edge_type, r.weight AS edge_weight, s.title AS section_title, s.toulmin_role AS role, substring(s.content, 0, 200) AS apprentice_context\n"
            "ORDER BY r.weight DESC;"
        ),
        "dialect": "cypher",
        "intent": "teachable_agent_gating",
        "keywords": ["teachable agent", "apprentice context", "naïve apprentice", "withhold solution", "sparring mode", "has_grounds", "has_rebuttal"],
        "complexity": "multi_hop",
    },
    {
        "id": "demo_018",
        "question": "Retrieve warrants ranked by epistemic weight for Productive Cognitive Friction",
        "query": (
            "MATCH (c:Concept {title: 'Productive Cognitive Friction'})-[e:HAS_WARRANT]->(w:Section)\n"
            "WHERE e.weight IS NOT NULL\n"
            "RETURN w.title AS warrant_title, e.weight AS epistemic_weight, w.modal_category AS certainty, substring(w.content, 0, 200) AS content_preview\n"
            "ORDER BY e.weight DESC;"
        ),
        "dialect": "cypher",
        "intent": "weighted_warrants",
        "keywords": ["warrants", "epistemic weight", "certainty", "ranked", "has_warrant", "weight", "mechanisms"],
        "complexity": "simple",
    },
    {
        "id": "demo_019",
        "question": "Find the strongest counter-arguments and rebuttals ranked by signed attack weight",
        "query": (
            "MATCH (c:Concept)-[e:HAS_REBUTTAL]->(reb:Section)\n"
            "WHERE e.signed_weight IS NOT NULL\n"
            "RETURN c.title AS concept, reb.title AS rebuttal, e.signed_weight AS attack_weight, reb.modal_category AS modal_category\n"
            "ORDER BY e.signed_weight ASC\n"
            "LIMIT 10;"
        ),
        "dialect": "cypher",
        "intent": "signed_rebuttal_ranking",
        "keywords": ["counter-arguments", "rebuttals", "signed weight", "attack weight", "has_rebuttal", "strongest attack"],
        "complexity": "simple",
    },
    {
        "id": "demo_020",
        "question": "Show high confidence empirical grounds and causal warrants above 0.75",
        "query": (
            "MATCH (c:Concept)-[e:HAS_GROUNDS|HAS_WARRANT]->(s:Section)\n"
            "WHERE e.weight >= 0.75\n"
            "RETURN c.title AS concept, s.title AS section, s.toulmin_role AS role, e.weight AS weight, s.modal_category AS certainty\n"
            "ORDER BY e.weight DESC\n"
            "LIMIT 10;"
        ),
        "dialect": "cypher",
        "intent": "high_confidence_toulmin",
        "keywords": ["high confidence", "certainty threshold", "weight threshold", "confidence above", "0.75", "has_grounds", "has_warrant"],
        "complexity": "simple",
    },
    {
        "id": "demo_021",
        "question": "Show modal certainty and average linguistic weight across Toulmin roles",
        "query": (
            "SELECT toulmin_role, modal_category, avg(weight) AS avg_weight, count(*) AS section_count\n"
            "FROM Section\n"
            "WHERE weight IS NOT NULL\n"
            "GROUP BY toulmin_role, modal_category\n"
            "ORDER BY avg_weight DESC;"
        ),
        "dialect": "sql",
        "intent": "modal_weight_distribution",
        "keywords": ["modal certainty", "average weight", "linguistic weight", "toulmin roles", "distribution"],
        "complexity": "simple",
    },
]


def init_dail_sql_schema(client: ArcadeDBClient) -> None:
    """Ensure TextToQueryDemo type, attributes, and indices exist."""
    print("  [*] Preparing TextToQueryDemo schema in ArcadeDB...")
    
    # 1. Create Document Type
    try:
        client.execute_command("CREATE DOCUMENT TYPE TextToQueryDemo IF NOT EXISTS")
        print("  [+] Document Type 'TextToQueryDemo' verified.")
    except Exception as e:
        print(f"  [i] Notice on CREATE DOCUMENT TYPE: {e}")

    # 2. Create Properties
    properties = [
        ("id", "STRING"),
        ("question", "STRING"),
        ("query", "STRING"),
        ("dialect", "STRING"),
        ("intent", "STRING"),
        ("keywords", "LIST OF STRING"),
        ("complexity", "STRING"),
    ]
    for prop, prop_type in properties:
        try:
            client.execute_command(f"CREATE PROPERTY TextToQueryDemo.{prop} IF NOT EXISTS {prop_type}")
        except Exception:
            pass

    # 3. Create Indices
    indices = [
        ("CREATE INDEX IF NOT EXISTS ON TextToQueryDemo (id) UNIQUE", "id unique index"),
        ("CREATE INDEX IF NOT EXISTS ON TextToQueryDemo (intent) NOTUNIQUE", "intent index"),
        ("CREATE INDEX IF NOT EXISTS ON TextToQueryDemo (dialect) NOTUNIQUE", "dialect index"),
    ]
    for cmd, desc in indices:
        try:
            client.execute_command(cmd)
            print(f"  [+] Created {desc}.")
        except Exception as e:
            if "already exists" in str(e).lower() or "unique" in str(e).lower():
                print(f"  [✓] {desc} active.")
            else:
                print(f"  [i] Notice on {desc}: {e}")

    # Full text index on question
    try:
        client.execute_command("CREATE INDEX IF NOT EXISTS ON TextToQueryDemo (question) FULL_TEXT")
        print("  [+] Created question full-text index.")
    except Exception as e:
        print(f"  [i] Notice on full-text index: {e}")


def seed_exemplars(client: ArcadeDBClient) -> int:
    """Seed or update all 12 verified exemplars."""
    print(f"  [*] Seeding {len(EXEMPLARS)} verified DAIL-SQL exemplars...")
    seeded_count = 0

    for demo in EXEMPLARS:
        demo_id = demo["id"]
        # Check if record exists
        existing = client.query(
            "SELECT FROM TextToQueryDemo WHERE id = :id",
            language="sql",
            params={"id": demo_id},
        )

        if existing:
            # Update existing
            client.execute_command(
                "UPDATE TextToQueryDemo SET question = :question, query = :query, dialect = :dialect, "
                "intent = :intent, keywords = :keywords, complexity = :complexity WHERE id = :id",
                language="sql",
                params=demo,
            )
        else:
            # Insert new document
            client.execute_command(
                "INSERT INTO TextToQueryDemo CONTENT " + json.dumps(demo),
                language="sql",
            )
        seeded_count += 1

    print(f"  [✓] Successfully seeded {seeded_count} exemplars.")
    return seeded_count


def verify_exemplars(client: ArcadeDBClient) -> bool:
    """Verify lookup by intent and total count."""
    print("  [*] Verifying TextToQueryDemo index and retrieval...")

    # 1. Total count
    records = client.query("SELECT count(*) AS total FROM TextToQueryDemo", language="sql")
    total = records[0].get("total", 0) if records else 0
    print(f"  [✓] Total TextToQueryDemo records: {total}")
    if total < 21:
        print(f"  [!] Expected at least 21 records, found {total}")
        return False

    # 2. Query by intent as specified in Phase 1: SELECT FROM TextToQueryDemo WHERE intent = 'cot_remedy_out'
    remedy_demo = client.query(
        "SELECT id, question, dialect, intent, query FROM TextToQueryDemo WHERE intent = 'cot_remedy_out'",
        language="sql",
    )
    if not remedy_demo:
        print("  [!] Failed to retrieve exemplar with intent 'cot_remedy_out'")
        return False

    demo = remedy_demo[0]
    print(f"  [✓] Successfully retrieved exemplar: id={demo.get('id')} | intent={demo.get('intent')} | dialect={demo.get('dialect')}")
    print(f"      Question: {demo.get('question')}")
    print(f"      Query:\n{demo.get('query')}")

    # 3. Retrieve Toulmin exemplar
    toulmin_demo = client.query(
        "SELECT id, question, dialect, intent, query FROM TextToQueryDemo WHERE intent = 'toulmin_warrant'",
        language="sql",
    )
    if toulmin_demo:
        tdemo = toulmin_demo[0]
        print(f"  [✓] Successfully retrieved Toulmin exemplar: id={tdemo.get('id')} | intent={tdemo.get('intent')}")
        print(f"      Question: {tdemo.get('question')}")
        print(f"      Query:\n{tdemo.get('query')}")

    # 4. Retrieve one SQL exemplar as well
    sql_demo = client.query(
        "SELECT id, question, dialect, intent, query FROM TextToQueryDemo WHERE intent = 'hybrid_search'",
        language="sql",
    )
    if sql_demo:
        sdemo = sql_demo[0]
        print(f"  [✓] Successfully retrieved SQL exemplar: id={sdemo.get('id')} | intent={sdemo.get('intent')}")
        print(f"      Question: {sdemo.get('question')}")

    return True


def main():
    print("=================================================================")
    print("  [Knowledge Lab] Phase 1: ArcadeDB DAIL-SQL Exemplar Seeding")
    print("=================================================================")

    client = ArcadeDBClient()
    if not client.is_ready():
        print(f"Error: ArcadeDB at {client.base_url} is not ready or unreachable.")
        sys.exit(1)

    init_dail_sql_schema(client)
    seed_exemplars(client)
    success = verify_exemplars(client)

    if success:
        print("=================================================================")
        print("  [✓] Phase 1 Complete: TextToQueryDemo is seeded and verified.")
        print("=================================================================")
    else:
        print("  [!] Phase 1 verification failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
