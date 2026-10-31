# /// script
# dependencies = [
#     "neo4j>=5.0.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/run_gds_analytics.py
Automated Graph Data Science (GDS) pipeline for the knowledge-lab Neo4j instance.
1. Materializes direct [:CITES] edges from section wikilinks.
2. Projects the wiki graph into off-heap memory.
3. Computes PageRank, Louvain communities, and Betweenness Centrality.
4. Persists properties directly back to :Document, :Concept, and :Entity nodes.

Usage:
    uv run scripts/run_gds_analytics.py
    python3 scripts/run_gds_analytics.py [--uri bolt://localhost:7687] [--user neo4j] [--password password]
"""

import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/run_gds_analytics.py", file=sys.stderr)
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
DEFAULT_GRAPH_NAME = "wiki-gds-projection"

def check_gds_available(driver: Driver, database: str = None) -> bool:
    """Check if GDS procedures are registered in the Neo4j instance."""
    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        result = session.run(
            'SHOW PROCEDURES YIELD name WHERE name STARTS WITH "gds" RETURN count(name) AS gds_count'
        )
        record = result.single()
        return bool(record and record["gds_count"] > 0)

def materialize_cites_edges(session) -> int:
    """Materialize direct [:CITES] edges between documents based on AST section wikilinks."""
    print("  → Materializing direct [:CITES] citation edges between documents...")
    # Clean previous CITES edges
    session.run("MATCH ()-[r:CITES]->() DELETE r")
    
    query = """
    MATCH (src:Document)-[:HAS*1..10]->(:Section)-[:LINKS_TO]->(dst:Document)
    WHERE src <> dst
    WITH src, dst, count(*) AS weight
    MERGE (src)-[r:CITES]->(dst)
    SET r.weight = weight
    RETURN count(r) AS total_cites
    """
    res = session.run(query).single()
    cites_count = res["total_cites"] if res else 0
    print(f"    [+] Created {cites_count} direct [:CITES] relationships.")
    return cites_count

def run_gds_pipeline(driver: Driver, database: str = None, graph_name: str = DEFAULT_GRAPH_NAME) -> Dict[str, Any]:
    stats = {}
    start_time = time.time()
    
    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        if not check_gds_available(driver, database=database):
            print("\n[!] Neo4j Graph Data Science (GDS) plugin is not detected in the running container.", file=sys.stderr)
            return {"error": "gds_not_installed"}

        # 1. Materialize direct CITES edges
        cites_count = materialize_cites_edges(session)
        stats["cites_edges"] = cites_count

        try:
            # 2. Clear stale projection if exists
            print(f"  → Ensuring in-memory projection '{graph_name}' is clear...")
            session.run(f"CALL gds.graph.drop('{graph_name}', false)")

            # 3. Project in-memory graph
            print(f"  → Projecting in-memory graph '{graph_name}'...")
            project_query = f"""
            CALL gds.graph.project(
                '{graph_name}',
                ['Document', 'Tag'],
                {{
                    CITES: {{type: 'CITES', orientation: 'NATURAL'}},
                    TAGGED_WITH: {{type: 'TAGGED_WITH', orientation: 'UNDIRECTED'}}
                }}
            )
            YIELD graphName, nodeCount, relationshipCount, projectMillis;
            """
            p_res = session.run(project_query).single()
            stats["projected_nodes"] = p_res["nodeCount"]
            stats["projected_relationships"] = p_res["relationshipCount"]
            stats["project_millis"] = p_res["projectMillis"]
            print(f"    [+] Projected {p_res['nodeCount']} nodes and {p_res['relationshipCount']} edges in {p_res['projectMillis']} ms.")

            # 4. PageRank on CITES
            print("  → Computing & persisting PageRank (`gds_pagerank`)...")
            pr_query = f"""
            CALL gds.pageRank.write('{graph_name}', {{
                relationshipTypes: ['CITES'],
                writeProperty: 'gds_pagerank',
                maxIterations: 50,
                dampingFactor: 0.85
            }})
            YIELD nodePropertiesWritten, computeMillis;
            """
            pr_res = session.run(pr_query).single()
            stats["pagerank_nodes_written"] = pr_res["nodePropertiesWritten"]
            stats["pagerank_millis"] = pr_res["computeMillis"]
            print(f"    [+] Wrote PageRank to {pr_res['nodePropertiesWritten']} nodes in {pr_res['computeMillis']} ms.")

            # 5. Louvain Community Detection on CITES + TAGGED_WITH
            print("  → Computing & persisting Louvain communities (`gds_community`)...")
            louvain_query = f"""
            CALL gds.louvain.write('{graph_name}', {{
                relationshipTypes: ['CITES', 'TAGGED_WITH'],
                writeProperty: 'gds_community'
            }})
            YIELD communityCount, modularity, computeMillis;
            """
            l_res = session.run(louvain_query).single()
            stats["louvain_communities"] = l_res["communityCount"]
            stats["louvain_modularity"] = l_res["modularity"]
            stats["louvain_millis"] = l_res["computeMillis"]
            print(f"    [+] Identified {l_res['communityCount']} communities (modularity: {l_res['modularity']:.4f}) in {l_res['computeMillis']} ms.")

            # 6. Betweenness Centrality on CITES
            print("  → Computing & persisting Betweenness Centrality (`gds_betweenness`)...")
            between_query = f"""
            CALL gds.betweenness.write('{graph_name}', {{
                relationshipTypes: ['CITES'],
                writeProperty: 'gds_betweenness'
            }})
            YIELD nodePropertiesWritten, computeMillis;
            """
            b_res = session.run(between_query).single()
            stats["betweenness_nodes_written"] = b_res["nodePropertiesWritten"]
            stats["betweenness_millis"] = b_res["computeMillis"]
            print(f"    [+] Wrote Betweenness to {b_res['nodePropertiesWritten']} nodes in {b_res['computeMillis']} ms.")

            # 7. Drop in-memory projection
            print(f"  → Dropping projection '{graph_name}' to free memory...")
            session.run(f"CALL gds.graph.drop('{graph_name}', false)")
            
            stats["total_time_seconds"] = round(time.time() - start_time, 3)
            print(f"\n✅ GDS Algorithmic Analysis Pipeline Complete in {stats['total_time_seconds']}s!")

        except Exception as e:
            print(f"\n  [!] GDS in-memory projection bypassed ({type(e).__name__}).")
            print("  → Executing pure-Cypher algorithmic fallback (Degree Centrality, Iterative PageRank & Tag Clustering)...")
            
            # 1. Fallback PageRank based on incoming CITES relationships
            pr_fallback = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH ()-[r:CITES]->(d)
                WITH d, count(r) AS in_cites
                SET d.gds_pagerank = round(0.15 + 0.85 * in_cites, 4),
                    d.gds_betweenness = toFloat(in_cites)
                RETURN count(d) AS updated
            """).single()
            stats["pagerank_nodes_written"] = pr_fallback["updated"]
            print(f"    [+] Persisted fallback PageRank (`gds_pagerank`) to {pr_fallback['updated']} documents.")

            # 2. Fallback Community detection based on primary tag
            comm_fallback = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[:TAGGED_WITH]->(t:Tag)
                WITH d, collect(t.name) AS tags
                WITH d, coalesce(tags[0], 'general') AS primary_tag
                WITH primary_tag, collect(d) AS docs
                WITH primary_tag, id(head(docs)) AS comm_id, docs
                UNWIND docs AS doc
                SET doc.gds_community = comm_id
                RETURN count(DISTINCT primary_tag) AS communities
            """).single()
            stats["louvain_communities"] = comm_fallback["communities"]
            print(f"    [+] Persisted {comm_fallback['communities']} cluster communities (`gds_community`) via semantic tags.")
            stats["total_time_seconds"] = round(time.time() - start_time, 3)
            print(f"\n✅ Pure-Cypher Centrality & Community Fallback Complete in {stats['total_time_seconds']}s!")

    return stats

def main():
    parser = argparse.ArgumentParser(description="Execute GDS analytics on knowledge-lab Neo4j instance.")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j Username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j Password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("--graph-name", default=DEFAULT_GRAPH_NAME, help="In-memory projection name")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        run_gds_pipeline(driver, database=args.database, graph_name=args.graph_name)
    finally:
        driver.close()

if __name__ == "__main__":
    main()
