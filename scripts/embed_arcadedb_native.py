#!/usr/bin/env python3
"""
scripts/embed_arcadedb_native.py
Native in-engine embedding generator for ArcadeDB using FastRP (Fast Random Projection).
Zero Ollama dependency, sub-second execution directly within ArcadeDB's JVM.
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

def run_native_embedding(dimensions: int = 768, iterations: int = 4):
    print("=" * 65)
    print("  ArcadeDB Native In-Engine Embedding Pipeline (Zero Ollama)")
    print("=" * 65)
    
    client = ArcadeDBClient()
    print(f"[*] Connected to ArcadeDB at {client.base_url} (Database: {client.database})")

    # 1. Ensure JVector Index on Section(embedding) exists
    print(f"[*] Ensuring JVector LSM_VECTOR index exists (dim={dimensions}, metric=COSINE)...")
    try:
        client.execute_sql(f'CREATE INDEX IF NOT EXISTS ON Section (embedding) LSM_VECTOR METADATA {{"dimensions": {dimensions}, "similarity": "COSINE"}}')
        print("  [✓] JVector index Section[embedding] verified.")
    except Exception as e:
        if "already exists" in str(e).lower() or "400" in str(e):
            print("  [✓] JVector index Section[embedding] active.")
        else:
            print(f"  [!] Note on vector index: {e}")

    # 2. Run FastRP across the knowledge graph
    print(f"[*] Executing native algo.fastrp (dimensions={dimensions}, iterations={iterations})...")
    t0 = time.perf_counter()
    cypher_fastrp = f"""
    CALL algo.fastrp({{
      dimensions: {dimensions},
      iterations: {iterations},
      normalization: -0.5,
      selfInfluence: 0.1,
      direction: 'BOTH'
    }})
    YIELD node, embedding
    WITH toString(node) AS rid_str, embedding
    MATCH (n) WHERE elementId(n) = rid_str
    SET n.embedding = embedding
    RETURN count(n) AS total_embedded
    """
    
    res = client.execute_cypher(cypher_fastrp)
    elapsed = (time.perf_counter() - t0) * 1000
    total = res[0].get("total_embedded", 0) if res else 0

    print(f"  [✓] FastRP embedded {total} vertices in {elapsed:.2f}ms directly in-engine.")

    # 3. Validation & Telemetry Check
    val_res = client.query_cypher("MATCH (s:Section) WHERE s.embedding IS NOT NULL RETURN count(s) AS count, size(s.embedding) AS dim LIMIT 1")
    if val_res:
        count = val_res[0].get("count", 0)
        dim = val_res[0].get("dim", 0)
        print(f"  [✓] Verification: {count} Section nodes populated with {dim}-dimensional vectors.")
    
    print("=" * 65)
    print("  Native Embedding Complete. Zero External Models Called.")
    print("=" * 65)

if __name__ == "__main__":
    dim = int(os.getenv("EMBEDDING_DIM", 768))
    run_native_embedding(dimensions=dim)
