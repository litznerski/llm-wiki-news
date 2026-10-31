#!/usr/bin/env python3
"""
scripts/run_arcadedb_analytics.py
Native Graph OLAP analytics runner for ArcadeDB in Knowledge Lab.
Computes PageRank, Betweenness Centrality, and Louvain Community Detection
directly inside ArcadeDB's engine without external GDS plugins or Neo4j dependencies.
"""

import os
import sys
import time
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

try:
    from scripts.arcadedb_client import ArcadeDBClient
except ImportError:
    sys.path.append(str(VAULT_ROOT))
    from scripts.arcadedb_client import ArcadeDBClient


def run_analytics():
    print("=" * 65)
    print("  ArcadeDB Native In-Engine Graph Analytics (Graph OLAP)")
    print("=" * 65)

    client = ArcadeDBClient()
    print(f"[*] Connected to ArcadeDB at {client.base_url} (Database: {client.database})")

    # 1. PageRank
    print("[*] Computing in-engine PageRank (dampingFactor=0.85, iterations=20)...")
    t0 = time.perf_counter()
    pr_res = client.execute_cypher("""
    CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 20, weightProperty: 'weight'})
    YIELD node, score
    WITH toString(node) AS rid_str, score
    MATCH (n) WHERE elementId(n) = rid_str
    SET n.pagerank = score
    RETURN count(n) AS total
    """)
    elapsed = (time.perf_counter() - t0) * 1000
    total = pr_res[0].get("total", 0) if pr_res else 0
    print(f"  [✓] PageRank materialized on {total} nodes in {elapsed:.2f}ms.")

    # 2. Betweenness Centrality
    print("[*] Computing in-engine Betweenness Centrality...")
    t0 = time.perf_counter()
    bw_res = client.execute_cypher("""
    CALL algo.betweenness()
    YIELD node, score
    WITH toString(node) AS rid_str, score
    MATCH (n) WHERE elementId(n) = rid_str
    SET n.betweenness = score
    RETURN count(n) AS total
    """)
    elapsed = (time.perf_counter() - t0) * 1000
    total = bw_res[0].get("total", 0) if bw_res else 0
    print(f"  [✓] Betweenness materialized on {total} nodes in {elapsed:.2f}ms.")

    # 3. Louvain Community Detection
    print("[*] Computing in-engine Louvain Community Detection...")
    t0 = time.perf_counter()
    lv_res = client.execute_cypher("""
    CALL algo.louvain()
    YIELD node, communityId
    WITH toString(node) AS rid_str, communityId
    MATCH (n) WHERE elementId(n) = rid_str
    SET n.community = communityId
    RETURN count(n) AS total
    """)
    elapsed = (time.perf_counter() - t0) * 1000
    total = lv_res[0].get("total", 0) if lv_res else 0
    print(f"  [✓] Louvain communities materialized on {total} nodes in {elapsed:.2f}ms.")

    # 4. Telemetry: Top Concepts by PageRank
    print("\n[*] Top 5 Concepts by In-Engine PageRank:")
    top_concepts = client.query_cypher("""
    MATCH (c:Concept)
    WHERE c.pagerank IS NOT NULL
    RETURN c.title AS title, c.pagerank AS pagerank, c.community AS community
    ORDER BY c.pagerank DESC
    LIMIT 5
    """)
    for rank, row in enumerate(top_concepts, 1):
        print(f"  {rank}. {row.get('title')} (score: {row.get('pagerank', 0):.4f}, comm: {row.get('community')})")

    print("=" * 65)
    print("  Graph Analytics Complete.")
    print("=" * 65)


if __name__ == "__main__":
    run_analytics()
