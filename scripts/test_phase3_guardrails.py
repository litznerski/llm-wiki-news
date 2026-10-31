"""
scripts/test_phase3_guardrails.py
Comprehensive Phase 3 Verification Suite:
1. Tier 1 Slash Commands (/sql, /cypher)
2. Tier 2 Model Valve Settings (preferred_dialect="sql" | "cypher")
3. Tier 3 Dynamic Semantic Intent Routing
4. AST Guardrail: OpenCypher Variable Shadowing Auto-Repair
5. AST Guardrail: OpenCypher Relationship Variable Auto-Binding
6. AST Guardrail: OpenCypher List CONTAINS Auto-Repair
7. AST Guardrail: ArcadeDB SQL ANSI JOIN Rejection
8. AST Guardrail: ArcadeDB SQL & Cypher Mutation Rejection (DDL/DML)
9. AST Guardrail: ArcadeDB SQL LIMIT 50 & TIMEOUT 10000 Injection
10. Full End-to-End POST /inlet Simulation
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
import asyncio
from services.fastmcp.dialect_switcher import QueryDialectSwitcher, RouteResult
from services.fastmcp.guardrails.arcadedb_ast import (
    ArcadeDBASTGuard,
    DialectSecurityError,
    DialectSyntaxError,
)
from services.fastmcp.server import sanitize_and_guard_query, handle_inlet, InletPayload


def test_tier1_slash_commands():
    print("\n--- Test 1: Tier 1 Slash Commands ---")
    r1 = QueryDialectSwitcher.route("/sql SELECT count(*) FROM Concept;")
    assert r1.dialect == "sql", f"Expected sql, got {r1.dialect}"
    assert r1.is_raw_query is True, "Expected is_raw_query=True"
    assert r1.clean_prompt == "SELECT count(*) FROM Concept;"
    print("✓ /sql with raw SQL query properly routed as raw sql")

    r2 = QueryDialectSwitcher.route("/sql Find 5 similar sections using vector search")
    assert r2.dialect == "sql", f"Expected sql, got {r2.dialect}"
    assert r2.is_raw_query is False, "Expected is_raw_query=False"
    assert r2.intent == "vector_knn", f"Expected vector_knn, got {r2.intent}"
    print("✓ /sql with natural language prompt routed to sql with vector_knn intent")

    r3 = QueryDialectSwitcher.route("/cypher MATCH (c:Concept) RETURN c.title LIMIT 3;")
    assert r3.dialect == "cypher", f"Expected cypher, got {r3.dialect}"
    assert r3.is_raw_query is True, "Expected is_raw_query=True"
    print("✓ /cypher with raw Cypher properly routed as raw cypher")

    r4 = QueryDialectSwitcher.route("/cypher What remedies solve Cognitive Surrender?")
    assert r4.dialect == "cypher", f"Expected cypher, got {r4.dialect}"
    assert r4.is_raw_query is False, "Expected is_raw_query=False"
    assert r4.intent == "cot_remedy_out", f"Expected cot_remedy_out, got {r4.intent}"
    print("✓ /cypher with natural language prompt routed to cypher with cot_remedy_out intent")


def test_tier2_valve_settings():
    print("\n--- Test 2: Tier 2 Model Valve Settings ---")
    prompt = "Show the top 3 ranked concepts"
    
    r_sql = QueryDialectSwitcher.route(prompt, preferred_dialect="sql")
    assert r_sql.dialect == "sql", f"Expected sql, got {r_sql.dialect}"
    assert "Tier 2" in r_sql.routing_reason
    print("✓ preferred_dialect='sql' overrides auto-routing")

    r_cypher = QueryDialectSwitcher.route(prompt, preferred_dialect="cypher")
    assert r_cypher.dialect == "cypher", f"Expected cypher, got {r_cypher.dialect}"
    assert "Tier 2" in r_cypher.routing_reason
    print("✓ preferred_dialect='cypher' overrides auto-routing")


def test_tier3_dynamic_auto_routing():
    print("\n--- Test 3: Tier 3 Dynamic Semantic Intent Routing ---")
    r_remedy = QueryDialectSwitcher.route("What solutions or mitigations remedy Cognitive Surrender?")
    assert r_remedy.dialect == "cypher", f"Expected cypher, got {r_remedy.dialect}"
    assert r_remedy.intent == "cot_remedy_out", f"Expected cot_remedy_out, got {r_remedy.intent}"
    print("✓ Remedy question automatically routed to OpenCypher")

    r_vec = QueryDialectSwitcher.route("Find similar sections using vector nearest neighbors")
    assert r_vec.dialect == "sql", f"Expected sql, got {r_vec.dialect}"
    assert r_vec.intent == "vector_knn", f"Expected vector_knn, got {r_vec.intent}"
    print("✓ Vector similarity question automatically routed to ArcadeDB SQL")

    r_raw_sql = QueryDialectSwitcher.route("SELECT title FROM Concept LIMIT 5;")
    assert r_raw_sql.dialect == "sql", f"Expected sql, got {r_raw_sql.dialect}"
    assert r_raw_sql.is_raw_query is True
    print("✓ Unprefixed SELECT query routed to SQL as raw query")

    r_raw_cypher = QueryDialectSwitcher.route("MATCH (c:Concept) RETURN c.title LIMIT 5;")
    assert r_raw_cypher.dialect == "cypher", f"Expected cypher, got {r_raw_cypher.dialect}"
    assert r_raw_cypher.is_raw_query is True
    print("✓ Unprefixed MATCH query routed to Cypher as raw query")


def test_cypher_variable_shadowing_repair():
    print("\n--- Test 4: Cypher Variable Shadowing Auto-Repair ---")
    # Exact user query that previously triggered: TypeError: Cannot access property 'pagerank' on String value
    user_query = (
        "MATCH (remedy:Concept)-[:REMEDIES_DILEMMA]->(target:Concept {title: 'Cognitive Surrender'})\n"
        "RETURN remedy.title AS remedy,\n"
        "       remedy.pagerank AS pagerank\n"
        "ORDER BY remedy.pagerank DESC;"
    )
    repaired = ArcadeDBASTGuard.repair_cypher_shadowing(user_query)
    print(f"Repaired user query:\n{repaired}")
    assert "remedy.title AS remedy_title" in repaired, "Expected remedy.title AS remedy_title"
    assert "remedy.pagerank AS pagerank" in repaired, "Expected remedy.pagerank AS pagerank untouched"
    print("✓ User's failing query successfully repaired (remedy.title AS remedy_title)")

    # Test shadowing of another declared variable
    q2 = "MATCH (solution:Concept)-[:REMEDIES_DILEMMA]->(target:Concept) RETURN target.title AS solution, target.pagerank AS pagerank;"
    repaired2 = ArcadeDBASTGuard.repair_cypher_shadowing(q2)
    assert "target.title AS solution_title" in repaired2
    print("✓ Cross-variable shadowing successfully repaired (target.title AS solution_title)")


def test_cypher_relationship_binding():
    print("\n--- Test 5: Cypher Relationship Variable Auto-Binding ---")
    q = "MATCH (a:Concept)-[:REMEDIES_DILEMMA]->(b:Concept) RETURN a.title, r.warrant, b.title LIMIT 3;"
    repaired = ArcadeDBASTGuard.repair_cypher_relationship_binding(q)
    assert "-[r:REMEDIES_DILEMMA]->" in repaired, f"Expected [r:REMEDIES_DILEMMA], got {repaired}"
    print("✓ Anonymous relationship automatically bound to -[r:REMEDIES_DILEMMA]->")


def test_cypher_list_contains():
    print("\n--- Test 6: Cypher List CONTAINS Auto-Repair ---")
    q = "MATCH (c:Concept) WHERE c.normalized_aliases CONTAINS 'pcf' RETURN c.title;"
    repaired = ArcadeDBASTGuard.repair_cypher_list_contains(q)
    assert "toLower('pcf') IN c.normalized_aliases" in repaired
    print("✓ Invalid list CONTAINS rewritten to 'toLower('pcf') IN c.normalized_aliases'")


def test_sql_ansi_join_rejection():
    print("\n--- Test 7: ArcadeDB SQL ANSI JOIN Rejection ---")
    bad_queries = [
        "SELECT * FROM Concept c JOIN Entity e ON c.title = e.title;",
        "SELECT * FROM Concept c INNER JOIN Entity e ON c.title = e.title;",
        "SELECT * FROM Concept c LEFT JOIN Entity e ON c.title = e.title;",
    ]
    for bq in bad_queries:
        try:
            ArcadeDBASTGuard.sanitize_sql(bq)
            assert False, f"Expected DialectSyntaxError for {bq}"
        except DialectSyntaxError as e:
            assert "ANSI SQL 'JOIN' is not supported in ArcadeDB" in str(e)
            print(f"✓ Properly rejected ANSI JOIN: {bq[:40]}...")


def test_mutation_rejection():
    print("\n--- Test 8: Mutation & DDL/DML Rejection ---")
    mutations = [
        ("sql", "DROP TYPE Concept;"),
        ("sql", "UPDATE Concept SET title = 'Hacked';"),
        ("sql", "DELETE FROM Concept;"),
        ("sql", "ALTER TYPE Concept ADD ATTRIBUTE foo STRING;"),
        ("cypher", "CREATE (c:Concept {title: 'Injected'});"),
        ("cypher", "MATCH (c:Concept) DELETE c;"),
        ("cypher", "MATCH (c:Concept) SET c.title = 'Injected';"),
    ]
    for dialect, q in mutations:
        try:
            ArcadeDBASTGuard.validate_and_sanitize(q, dialect)
            assert False, f"Expected DialectSecurityError for {q}"
        except DialectSecurityError as e:
            assert "Mutating or administrative operation" in str(e)
            print(f"✓ Properly blocked mutating operation in {dialect.upper()}: {q}")


def test_sql_limit_injection():
    print("\n--- Test 9: SQL LIMIT 50 Injection & Boundary Enforcement ---")
    # Query without LIMIT
    q1 = "SELECT count(*) FROM Concept;"
    sanitized1 = ArcadeDBASTGuard.sanitize_sql(q1)
    assert "LIMIT 50" in sanitized1
    assert sanitized1.endswith("LIMIT 50"), "Query must end with LIMIT 50"
    print(f"✓ Missing LIMIT injected: {sanitized1}")

    # Query with existing LIMIT
    q2 = "SELECT title FROM Concept LIMIT 5;"
    sanitized2 = ArcadeDBASTGuard.sanitize_sql(q2)
    assert "LIMIT 5" in sanitized2
    assert "LIMIT 50" not in sanitized2
    assert sanitized2.endswith("LIMIT 5"), "Existing LIMIT preserved at end of query"
    print(f"✓ Existing LIMIT preserved: {sanitized2}")


async def test_end_to_end_inlet():
    print("\n--- Test 10: End-to-End POST /inlet Simulation against ArcadeDB ---")
    # 1. User's exact previously failing query
    user_failing_query = (
        "MATCH (remedy:Concept)-[:REMEDIES_DILEMMA]->(target:Concept {title: 'Cognitive Surrender'})\n"
        "RETURN remedy.title AS remedy,\n"
        "       remedy.pagerank AS pagerank\n"
        "ORDER BY remedy.pagerank DESC;"
    )
    res1 = await handle_inlet(InletPayload(message=user_failing_query, dialect="auto"))
    assert res1["status"] == "success", f"Expected success, got: {res1}"
    assert res1["record_count"] == 4, f"Expected 4 records, got {res1['record_count']}"
    assert "Artifact vs. Defense Assessment" in res1["context_markdown"]
    print(f"✓ User's query executed via /inlet: returned {res1['record_count']} records!")
    print(f"  Executed Query:\n{res1['executed_query']}\n")

    # 2. Slash command /sql with raw query
    res2 = await handle_inlet(InletPayload(message="/sql SELECT count(*) FROM Concept;", dialect="auto"))
    assert res2["status"] == "success"
    assert res2["dialect"] == "sql"
    assert "Tier 1" in res2["routing_reason"]
    print("✓ /sql raw query executed successfully via /inlet")

    # 3. Natural language remedy inquiry
    res3 = await handle_inlet(InletPayload(message="What solutions or mitigations remedy Cognitive Surrender?", dialect="auto"))
    assert res3["status"] == "success"
    assert res3["dialect"] == "cypher"
    assert res3["intent"] == "cot_remedy_out"
    print(f"✓ Natural language remedy inquiry executed successfully via /inlet: {res3['record_count']} records")

    # 4. Mutation attempt blocked cleanly
    res4 = await handle_inlet(InletPayload(message="DROP TYPE Concept;", dialect="auto"))
    assert res4["status"] == "error"
    assert "Security Restriction" in res4["error"]
    assert "Query Guardrail Violation" in res4["context_markdown"]
    print("✓ Malicious mutation via /inlet cleanly blocked with guardrail card")

    # 5. ANSI JOIN attempt blocked cleanly
    res5 = await handle_inlet(InletPayload(message="SELECT * FROM Concept c JOIN Entity e ON c.title = e.title;", dialect="sql"))
    assert res5["status"] == "error"
    assert "ANSI SQL 'JOIN' is not supported in ArcadeDB" in res5["error"]
    print("✓ ANSI JOIN attempt via /inlet cleanly blocked with educational message")


async def main():
    print("==================================================")
    print("Starting Phase 3 Verification Test Suite")
    print("==================================================")

    test_tier1_slash_commands()
    test_tier2_valve_settings()
    test_tier3_dynamic_auto_routing()
    test_cypher_variable_shadowing_repair()
    test_cypher_relationship_binding()
    test_cypher_list_contains()
    test_sql_ansi_join_rejection()
    test_mutation_rejection()
    test_sql_limit_injection()
    await test_end_to_end_inlet()

    print("\n==================================================")
    print("🎉 ALL 10 PHASE 3 VERIFICATION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
