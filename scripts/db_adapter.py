#!/usr/bin/env python3
"""
scripts/db_adapter.py
Universal Database Adapter for Knowledge Lab.
Inspects active environment configuration (.env) and provides a unified interface
for executing Cypher and graph queries across Neo4j (Local/Aura) and ArcadeDB.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class GraphDatabaseAdapter:
    """Unified graph query adapter routing to Neo4j or ArcadeDB based on GRAPH_BACKEND."""

    def __init__(self):
        self.backend = os.getenv("GRAPH_BACKEND", "neo4j").lower()
        self.target = os.getenv("ACTIVE_TARGET", "neo4j-local").lower()

    def is_arcadedb(self) -> bool:
        return self.backend == "arcadedb"

    def is_neo4j(self) -> bool:
        return self.backend == "neo4j"

    def execute_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a Cypher query against the active database backend."""
        if self.is_arcadedb():
            try:
                from scripts.arcadedb_client import ArcadeDBClient
            except ImportError:
                sys.path.append(str(VAULT_ROOT))
                from scripts.arcadedb_client import ArcadeDBClient

            client = ArcadeDBClient()
            # If query is state-modifying (CREATE, SET, DELETE, MERGE, CALL algo)
            q_upper = query.strip().upper()
            if any(q_upper.startswith(w) for w in ("CREATE", "MERGE", "SET", "DELETE", "DROP", "ALTER")) or "SET " in q_upper:
                return client.execute_cypher(query, params=params)
            return client.query_cypher(query, params=params)
        else:
            try:
                from neo4j import GraphDatabase
            except ImportError:
                raise RuntimeError("Neo4j driver required. Run: pip install neo4j")

            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            pwd = os.getenv("NEO4J_PASSWORD", "password")
            db = os.getenv("NEO4J_DATABASE")

            with GraphDatabase.driver(uri, auth=(user, pwd)) as driver:
                session_kwargs = {"database": db} if db else {}
                with driver.session(**session_kwargs) as session:
                    res = session.run(query, params or {})
                    return [r.data() for r in res]


if __name__ == "__main__":
    adapter = GraphDatabaseAdapter()
    print("=" * 65)
    print(f"  Active Graph Backend : {adapter.backend.upper()}")
    print(f"  Active Target Config : {adapter.target}")
    print("=" * 65)
    
    test_cypher = "MATCH (c:Concept) RETURN count(c) AS concept_count"
    try:
        results = adapter.execute_cypher(test_cypher)
        count = results[0].get("concept_count", 0) if results else 0
        print(f"  [✓] Test Cypher Query Succeeded: Found {count} concepts.")
    except Exception as e:
        print(f"  [!] Query Error: {e}", file=sys.stderr)
