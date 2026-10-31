#!/usr/bin/env python3
"""
scripts/recompute_weights.py
Executes in-engine Cypher weight propagation and weighted PageRank re-computation
directly inside ArcadeDB in < 200ms.
"""

import sys
import time
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(VAULT_ROOT))

from scripts.arcadedb_client import ArcadeDBClient


def recompute_weights():
    client = ArcadeDBClient()
    print("=" * 65)
    print("  ArcadeDB In-Engine Weight Propagation & Graph OLAP Recomputation")
    print(f"  Target Database: {client.database} @ {client.base_url}")
    print("=" * 65)

    t0 = time.perf_counter()

    # 1. Toulmin Edge Weight Propagation
    print("[1/3] Propagating section weights to Toulmin containment edges...")
    cypher_toulmin = """
    MATCH (c:Concept)-[e:HAS_GROUNDS|HAS_WARRANT|HAS_CLAIM|HAS_REBUTTAL|HAS_SOLUTION|HAS_QUALIFIER|HAS_BACKING]->(s:Section)
    WHERE s.weight IS NOT NULL
    SET e.weight = s.weight
    RETURN count(e) AS updated_edges
    """
    res1 = client.execute_cypher(cypher_toulmin)
    count1 = res1[0].get("updated_edges", 0) if res1 else 0
    print(f"  [✓] Updated {count1} Toulmin containment edges.")

    # 2. Signed Weight on Rebuttal Edges
    print("[2/3] Materializing negative signed weights on HAS_REBUTTAL attack edges...")
    cypher_signed = """
    MATCH (c:Concept)-[e:HAS_REBUTTAL]->(s:Section)
    WHERE s.weight IS NOT NULL
    SET e.signed_weight = -1.0 * s.weight
    RETURN count(e) AS signed_edges
    """
    res2 = client.execute_cypher(cypher_signed)
    count2 = res2[0].get("signed_edges", 0) if res2 else 0
    print(f"  [✓] Materialized signed weights across {count2} HAS_REBUTTAL edges.")

    # 3. Weighted PageRank Calculation
    print("[3/3] Recomputing weighted PageRank via algo.pagerank in-engine...")
    cypher_pr = """
    CALL algo.pagerank({dampingFactor: 0.85, maxIterations: 20, weightProperty: 'weight'})
    YIELD node, score
    WITH toString(node) AS rid_str, score
    MATCH (n) WHERE elementId(n) = rid_str
    SET n.pagerank = score
    RETURN count(n) AS total_pagerank
    """
    res3 = client.execute_cypher(cypher_pr)
    count3 = res3[0].get("total_pagerank", 0) if res3 else 0
    print(f"  [✓] Weighted PageRank materialized across {count3} nodes.")

    elapsed = (time.perf_counter() - t0) * 1000
    print("=" * 65)
    print(f"  [✓] Complete in {elapsed:.2f}ms. Zero external dependencies invoked.")
    print("=" * 65)


if __name__ == "__main__":
    recompute_weights()
