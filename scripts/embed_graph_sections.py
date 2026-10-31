# /// script
# dependencies = [
#     "neo4j>=5.0.0",
#     "httpx>=0.25.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/embed_graph_sections.py
Embeds all (s:Section) nodes in Neo4j using local Ollama (nomic-embed-text)
and initializes the native Neo4j HNSW Vector Index.

Usage:
    uv run scripts/embed_graph_sections.py
    python3 scripts/embed_graph_sections.py [--ollama-url http://127.0.0.1:11434/api/embeddings]
"""

import os
import sys
import time
import re
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
from typing import List, Dict, Any, Optional

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    print("Error: The 'neo4j' Python driver is required.", file=sys.stderr)
    print("Run with uv:  uv run scripts/embed_graph_sections.py", file=sys.stderr)
    print("Or install:   pip install neo4j httpx", file=sys.stderr)
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

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_EMBED_URL", "http://127.0.0.1:11434/api/embed")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIM = 768
BATCH_SIZE = 64

MERMAID_REGEX = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
NODE_LABEL_REGEX = re.compile(r'([A-Za-z0-9_\-]+)(?:\["([^"]+)"\]|\[([^\]]+)\]|\("([^"]+)"\)|\(([^)]+)\))')

def clean_section_for_embedding(text: str) -> str:
    """Strip raw Mermaid syntax and substitute with semantic sequence transcript."""
    def replacer(match: re.Match) -> str:
        raw_code = match.group(1).strip()
        labels = []
        for m in NODE_LABEL_REGEX.finditer(raw_code):
            lbl = m.group(2) or m.group(3) or m.group(4) or m.group(5)
            if lbl:
                clean_lbl = lbl.replace("<br/>", " - ").replace("<br>", " - ").strip()
                if clean_lbl and clean_lbl not in labels:
                    labels.append(clean_lbl)
        if labels:
            return "Visual flow: " + " -> ".join(labels[:6]) + ". "
        return "Visual conceptual architecture. "

    cleaned = MERMAID_REGEX.sub(replacer, text)
    return cleaned.strip()[:2048] if cleaned.strip() else " "


def get_batch_embeddings(client: httpx.Client, ollama_url: str, texts: List[str]) -> List[List[float]]:
    """Generate 768-dim vector embeddings via Ollama native batch /api/embed with fallback."""
    clean_texts = [clean_section_for_embedding(t) for t in texts]
    if not clean_texts:
        return []

    # If endpoint points to /api/embed, use native batch array
    if ollama_url.endswith("/api/embed"):
        try:
            resp = client.post(ollama_url, json={"model": EMBEDDING_MODEL, "input": clean_texts}, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                embs = data.get("embeddings", [])
                if len(embs) == len(clean_texts):
                    return embs
        except Exception:
            pass  # Fall through to legacy endpoint

    # Fallback to legacy /api/embeddings (single or loop)
    legacy_url = ollama_url.replace("/api/embed", "/api/embeddings")
    results = []
    for ct in clean_texts:
        try:
            resp = client.post(legacy_url, json={"model": EMBEDDING_MODEL, "prompt": ct}, timeout=30.0)
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        except Exception as e:
            print(f"    [!] Error in fallback embedding: {e}", file=sys.stderr)
            results.append([0.0] * EMBEDDING_DIM)
    return results

def run_embedding_pipeline(driver: Driver, database: str = DEFAULT_DATABASE, ollama_url: str = DEFAULT_OLLAMA_URL, force: bool = False):
    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # 1. Create Vector Index if not exists
        print(f"[*] Ensuring native Vector Index 'section_vector_idx' exists (dim={EMBEDDING_DIM})...")
        session.run(f"""
        CREATE VECTOR INDEX section_vector_idx IF NOT EXISTS
        FOR (s:Section) ON (s.embedding)
        OPTIONS {{indexConfig: {{
          `vector.dimensions`: {EMBEDDING_DIM},
          `vector.similarity_function`: 'cosine'
        }}}}
        """)
        print("    [+] Native Vector Index 'section_vector_idx' is ready.")

        # 2. Fetch sections requiring vector embeddings
        print("[*] Querying sections requiring vector embeddings...")
        where_clause = "WHERE s.content IS NOT NULL AND size(trim(s.content)) > 20"
        if not force:
            where_clause += " AND s.embedding IS NULL"

        records = session.run(f"""
            MATCH (s:Section)
            {where_clause}
            OPTIONAL MATCH (d:Document)-[:HAS*1..3]->(s)
            WITH s, head(collect(d)) AS d
            RETURN elementId(s) AS id,
                   coalesce(s.displayName, s.title, s.name, 'Section') AS title,
                   s.content AS content,
                   coalesce(s.step_type, 'NARRATIVE_STEP') AS step_type,
                   d.type AS doc_type,
                   coalesce(labels(d), []) AS doc_labels
        """).data()

        total = len(records)
        print(f"    [+] Found {total} sections needing embedding.")
        if total == 0:
            print("[✓] All sections are already embedded. Vector store is up to date.")
            return

        # 3. Native batch embedding pipeline
        start_time = time.time()
        embedded_count = 0

        with httpx.Client(timeout=60.0) as client:
            for i in range(0, total, BATCH_SIZE):
                batch = records[i:i + BATCH_SIZE]
                prompts = []
                for item in batch:
                    doc_type = item.get("doc_type")
                    doc_labels = item.get("doc_labels") or []
                    step_type = item.get("step_type", "NARRATIVE_STEP")
                    if doc_type == "entity" or "Entity" in doc_labels:
                        role_prefix = f"[ENTITY_ROLE: {step_type}]"
                    else:
                        role_prefix = f"[{step_type}]"
                    prompts.append(f"{role_prefix} {item['title']}: {item['content']}")

                vectors = get_batch_embeddings(client, ollama_url, prompts)
                updates = [
                    {"id": item["id"], "vec": vec}
                    for item, vec in zip(batch, vectors)
                    if vec and any(vec)
                ]

                if updates:
                    session.run("""
                        UNWIND $updates AS row
                        MATCH (s:Section) WHERE elementId(s) = row.id
                        SET s.embedding = row.vec
                    """, updates=updates)

                embedded_count += len(batch)
                percent = (embedded_count / total) * 100
                elapsed_so_far = time.time() - start_time
                rate = embedded_count / elapsed_so_far if elapsed_so_far > 0 else 0
                print(f"    [*] Progress: {embedded_count}/{total} sections ({percent:.1f}%) · {rate:.1f} sec/s...")

        elapsed = time.time() - start_time
        overall_rate = embedded_count / elapsed if elapsed > 0 else 0
        print(f"\n[✓] Successfully embedded {embedded_count} sections in {elapsed:.2f}s ({overall_rate:.1f} sections/sec).")

def main():
    parser = argparse.ArgumentParser(description="Embed Neo4j Section nodes using local Ollama nomic-embed-text.")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j Username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j Password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama embeddings endpoint")
    parser.add_argument("--force", action="store_true", help="Force re-embedding of all sections with epistemic prefixes")
    args = parser.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), max_connection_lifetime=60)
    try:
        run_embedding_pipeline(driver, database=args.database, ollama_url=args.ollama_url, force=args.force)
    finally:
        driver.close()

if __name__ == "__main__":
    main()
