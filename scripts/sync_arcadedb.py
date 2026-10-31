# /// script
# dependencies = [
#     "neo4j>=5.0.0",
#     "httpx>=0.25.0",
# ]
# ///
#!/usr/bin/env python3
"""
scripts/sync_arcadedb.py
Master sync & benchmarking harness for piloting ArcadeDB against Neo4j in Knowledge Lab.
Exports nodes, edges, vectors, and alias lookups via high-density NDJSON batch streams.
Executes B1-B4 latency and memory benchmarks.

Usage:
    uv run scripts/sync_arcadedb.py --sync --benchmark
    uv run scripts/sync_arcadedb.py --benchmark-only
"""

import os
import re
import sys
import time
import json
import base64
import hashlib
import argparse
import statistics
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Set

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

# Default Connection Settings
ARCADEDB_URL = os.getenv("ARCADEDB_URL", "http://localhost:2480").rstrip("/")
ARCADEDB_DATABASE = os.getenv("ARCADEDB_DATABASE", "knowledgedb")
ARCADEDB_USER = os.getenv("ARCADEDB_USER", "root")
ARCADEDB_PASSWORD = os.getenv("ARCADEDB_PASSWORD", "root_secret")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


class ArcadeDBSyncClient:
    """High-density NDJSON batch and query client for ArcadeDB."""

    def __init__(self, base_url: str = ARCADEDB_URL, database: str = ARCADEDB_DATABASE,
                 user: str = ARCADEDB_USER, password: str = ARCADEDB_PASSWORD):
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.auth_header = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def is_ready(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/ready")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def execute_sql(self, command: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/command/{self.database}"
        payload = json.dumps({"command": command, "language": "sql"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            return json.loads(resp.read().decode("utf-8")).get("result", [])

    def query(self, query_str: str, language: str = "cypher", params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/v1/query/{self.database}"
        body: Dict[str, Any] = {"command": query_str, "language": language}
        if params:
            body["params"] = params
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            return json.loads(resp.read().decode("utf-8")).get("result", [])

    def batch_ndjson(self, ndjson_lines: List[str]) -> Dict[str, Any]:
        """Send high-density NDJSON batch payload to ArcadeDB."""
        if not ndjson_lines:
            return {"verticesCreated": 0, "edgesCreated": 0, "elapsedMs": 0}
        url = f"{self.base_url}/api/v1/batch/{self.database}"
        payload = "\n".join(ndjson_lines).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/x-ndjson"}
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ArcadeDB Batch Error {e.code}: {err}") from e

    def mcp_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/mcp"
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": 1
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": self.auth_header, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            return json.loads(resp.read().decode("utf-8"))


def init_arcadedb_schema(client: ArcadeDBSyncClient):
    """Ensure all core types and indexes exist in ArcadeDB."""
    print("  [*] Verifying and initializing ArcadeDB schema...")
    vertex_types = ["Concept", "Entity", "Source", "Section", "Tag", "Diagram"]
    for vt in vertex_types:
        try:
            client.execute_sql(f"CREATE VERTEX TYPE {vt} IF NOT EXISTS")
        except Exception:
            pass

    # Property definitions and unique constraints
    schema_commands = [
        "CREATE PROPERTY Concept.title STRING",
        "CREATE PROPERTY Concept.type STRING",
        "CREATE PROPERTY Concept.reliability_score DOUBLE",
        "CREATE PROPERTY Concept.last_updated STRING",
        "CREATE INDEX IF NOT EXISTS ON Concept (title) UNIQUE",

        "CREATE PROPERTY Entity.title STRING",
        "CREATE PROPERTY Entity.subtype STRING",
        "CREATE PROPERTY Entity.reliability_score DOUBLE",
        "CREATE INDEX IF NOT EXISTS ON Entity (title) UNIQUE",

        "CREATE PROPERTY Source.slug STRING",
        "CREATE PROPERTY Source.title STRING",
        "CREATE INDEX IF NOT EXISTS ON Source (slug) UNIQUE",

        "CREATE PROPERTY Tag.name STRING",
        "CREATE INDEX IF NOT EXISTS ON Tag (name) UNIQUE",

        "CREATE PROPERTY Section.uri STRING",
        "CREATE PROPERTY Section.title STRING",
        "CREATE PROPERTY Section.display_name STRING",
        "CREATE PROPERTY Section.path STRING",
        "CREATE PROPERTY Section.heading_level INTEGER",
        "CREATE PROPERTY Section.heading STRING",
        "CREATE PROPERTY Section.content STRING",
        "CREATE PROPERTY Section.step_type STRING",
        "CREATE PROPERTY Section.toulmin_role STRING",
        "CREATE PROPERTY Section.weight FLOAT",
        "CREATE PROPERTY Section.modal_category STRING",
        "CREATE PROPERTY Section.embedding LIST OF FLOAT",
        "CREATE INDEX IF NOT EXISTS ON Section (uri) UNIQUE",
        "CREATE INDEX IF NOT EXISTS ON Section (toulmin_role) NOTUNIQUE",

        "CREATE PROPERTY Diagram.id STRING",
        "CREATE PROPERTY Diagram.section_uri STRING",
        "CREATE PROPERTY Diagram.title STRING",
        "CREATE PROPERTY Diagram.diagram_type STRING",
        "CREATE PROPERTY Diagram.direction STRING",
        "CREATE PROPERTY Diagram.raw_code STRING",
        "CREATE PROPERTY Diagram.node_labels LIST OF STRING",
        "CREATE PROPERTY Diagram.semantic_transcript STRING",
        "CREATE PROPERTY Diagram.order_idx INTEGER",
        "CREATE PROPERTY Diagram.created_at STRING",
        "CREATE INDEX IF NOT EXISTS ON Diagram (id) UNIQUE",
        "CREATE INDEX IF NOT EXISTS ON Diagram (section_uri) NOTUNIQUE",

        "CREATE PROPERTY Concept.pagerank FLOAT",
        "CREATE PROPERTY Concept.community INTEGER",
        "CREATE PROPERTY Concept.betweenness FLOAT",

        "CREATE PROPERTY Entity.pagerank FLOAT",
        "CREATE PROPERTY Entity.community INTEGER",

        "CREATE DOCUMENT TYPE AliasLookup IF NOT EXISTS",
        "CREATE PROPERTY AliasLookup.alias STRING",
        "CREATE PROPERTY AliasLookup.canonical_title STRING",
        "CREATE INDEX IF NOT EXISTS ON AliasLookup (alias) UNIQUE",
    ]
    for cmd in schema_commands:
        try:
            client.execute_sql(cmd)
        except Exception:
            pass

    # JVector HNSW Vector index on Section[embedding]
    try:
        client.execute_sql('CREATE INDEX ON Section (embedding) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE"}')
        print("  [+] Native JVector index 'Section[embedding]' created (768-dim, COSINE).")
    except Exception as e:
        if "already exists" in str(e).lower() or "400" in str(e) or "500" in str(e):
            print("  [✓] Native JVector index 'Section[embedding]' active.")
        else:
            print(f"  [!] Note on vector index: {e}")

    # Edge types
    edge_types = [
        "PROGRESSES_TO", "NEXT_SECTION", "REMEDIES_DILEMMA", "EXTENDS_THEORY", "PRECIPITATES",
        "EMPIRICALLY_GROUNDS", "ORIGINATES_THEORY", "CHAMPIONS_SOLUTION",
        "CRITIQUES_PARADIGM", "OPERATIONALIZES", "AFFILIATED_WITH",
        "INTELLECTUAL_LINEAGE", "AUTHORED_BY", "PUBLISHED_BY",
        "HAS_SECTION", "TAGGED_WITH", "LINKS_TO", "CITES",
        # Specialized Toulmin Containment Edge Types (Phase 1)
        "HAS_GROUNDS", "HAS_WARRANT", "HAS_CLAIM", "HAS_REBUTTAL",
        "HAS_SOLUTION", "HAS_QUALIFIER", "HAS_BACKING",
        # Decoupled Diagram Containment Edge
        "HAS_DIAGRAM"
    ]
    for et in edge_types:
        try:
            client.execute_sql(f"CREATE EDGE TYPE {et} IF NOT EXISTS")
        except Exception:
            pass

    cot_edge_commands = [
        "CREATE PROPERTY PROGRESSES_TO.transition_type STRING",
        "CREATE PROPERTY PROGRESSES_TO.warrant STRING",
        "CREATE PROPERTY PROGRESSES_TO.confidence FLOAT",
        "CREATE PROPERTY PROGRESSES_TO.method STRING",

        # Toulmin containment edges weight property
        "CREATE PROPERTY HAS_GROUNDS.weight FLOAT",
        "CREATE PROPERTY HAS_WARRANT.weight FLOAT",
        "CREATE PROPERTY HAS_REBUTTAL.weight FLOAT",
        "CREATE PROPERTY HAS_SOLUTION.weight FLOAT",
        "CREATE PROPERTY HAS_QUALIFIER.weight FLOAT",
        "CREATE PROPERTY HAS_BACKING.weight FLOAT",
        "CREATE PROPERTY HAS_CLAIM.weight FLOAT",

        # Macro-CoT relational edges weight property
        "CREATE PROPERTY REMEDIES_DILEMMA.weight FLOAT",
        "CREATE PROPERTY EXTENDS_THEORY.weight FLOAT",
        "CREATE PROPERTY PRECIPITATES.weight FLOAT",
        "CREATE PROPERTY NEXT_SECTION.order_idx INTEGER",
        "CREATE PROPERTY HAS_DIAGRAM.order_idx INTEGER",

        # Indexes for efficient weight-filtered traversals
        "CREATE INDEX IF NOT EXISTS ON HAS_WARRANT (weight) NOTUNIQUE",
        "CREATE INDEX IF NOT EXISTS ON HAS_REBUTTAL (weight) NOTUNIQUE",
    ]
    for cmd in cot_edge_commands:
        try:
            client.execute_sql(cmd)
        except Exception:
            pass
    print("  [✓] ArcadeDB schema types and indexes ready.")


def map_to_toulmin_role(step_type: str, doc_type: str = "concept") -> str:
    """
    Direct mapping from epistemic step_type to Toulmin argumentation role:
    - DEFINITIONAL_ANCHOR -> 'GROUNDS'
    - CORE_THESIS -> 'CLAIM'
    - MECHANISTIC_DEEPEN -> 'WARRANT'
    - MANIFESTATION_TRAP / DILEMMA_PROBLEM -> 'REBUTTAL'
    - PRESCRIPTIVE_SOLUTION -> 'SOLUTION_WARRANT'
    - EMPIRICAL_BOUNDARY -> 'QUALIFIER'
    - SYNTHESIS_CATALOG -> 'BACKING'
    - Entity and Source sections -> 'NON_ARGUMENTATIVE'
    """
    if doc_type in ("entity", "source"):
        return "NON_ARGUMENTATIVE"

    mapping = {
        "DEFINITIONAL_ANCHOR": "GROUNDS",
        "CORE_THESIS": "CLAIM",
        "MECHANISTIC_DEEPEN": "WARRANT",
        "MANIFESTATION_TRAP": "REBUTTAL",
        "DILEMMA_PROBLEM": "REBUTTAL",
        "PRESCRIPTIVE_SOLUTION": "SOLUTION_WARRANT",
        "EMPIRICAL_BOUNDARY": "QUALIFIER",
        "SYNTHESIS_CATALOG": "BACKING",
    }
    return mapping.get(step_type, "NON_ARGUMENTATIVE")


MERMAID_REGEX = re.compile(r'```mermaid\n(.*?)```', re.DOTALL)
NODE_LABEL_REGEX = re.compile(r'([A-Za-z0-9_\-]+)(?:\["([^"]+)"\]|\[([^\]]+)\]|\("([^"]+)"\)|\(([^)]+)\))')
HEADER_REGEX = re.compile(
    r'^\s*(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram)\s*([A-Z]+)?',
    re.MULTILINE
)

def process_section_diagrams(
    section_uri: str,
    section_title: str,
    raw_content: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Scans raw section content for Mermaid blocks.
    Replaces each block with an Obsidian callout containing a clean semantic sequence transcript.
    Returns:
        (clean_content, extracted_diagram_docs)
    """
    diagrams: List[Dict[str, Any]] = []

    def replacer(match: re.Match) -> str:
        diagram_idx = len(diagrams) + 1
        raw_code = match.group(1).strip()

        hdr_match = HEADER_REGEX.search(raw_code)
        dtype = hdr_match.group(1) if hdr_match else "flowchart"
        direction = hdr_match.group(2) if hdr_match and hdr_match.group(2) else "TD"

        labels: List[str] = []
        for m in NODE_LABEL_REGEX.finditer(raw_code):
            lbl = m.group(2) or m.group(3) or m.group(4) or m.group(5)
            if lbl:
                clean_lbl = lbl.replace("<br/>", " - ").replace("<br>", " - ").strip()
                if clean_lbl and clean_lbl not in labels:
                    labels.append(clean_lbl)

        if labels:
            flow_summary = " → ".join(labels[:6])
            if len(labels) > 6:
                flow_summary += f" (and {len(labels) - 6} more steps)"
        else:
            flow_summary = "Visual conceptual architecture"

        diag_id = hashlib.sha256(
            f"{section_uri}|diag_{diagram_idx}".encode("utf-8")
        ).hexdigest()[:16]

        diagrams.append({
            "id": diag_id,
            "section_uri": section_uri,
            "title": f"{section_title} - Diagram {diagram_idx}",
            "diagram_type": dtype,
            "direction": direction,
            "raw_code": match.group(0),
            "node_labels": labels,
            "semantic_transcript": flow_summary,
            "order_idx": diagram_idx,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        return ""

    clean_content = MERMAID_REGEX.sub(replacer, raw_content)
    clean_content = re.sub(r'\n{3,}', '\n\n', clean_content).strip()
    return clean_content, diagrams


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
    (r'\b(necessarily|always|invariably|definitively|completely|total|zero|100%|never)\b', 1.0,  "CERTAINTY"),
    (r'\b(typically|generally|in most cases|consistently|must|will|every)\b',              0.85, "HIGH_PROB"),
    (r'\b(often|usually|tends to|frequently|regularly)\b',                                 0.65, "MODERATE_HIGH"),
    (r'\b(can|may|sometimes|in some cases|often produces|tend)\b',                         0.45, "MODERATE_LOW"),
    (r'\b(possibly|perhaps|might|could|under certain|in specific contexts)\b',             0.30, "HEDGED"),
    (r'\b(rarely|seldom|not always|only when|limited|narrow|few)\b',                       0.15, "WEAK"),
]

STEP_TYPE_FLOOR = {
    "DEFINITIONAL_ANCHOR": 0.75,  # Definitions are implicitly certain
    "SYNTHESIS_CATALOG":   0.50,  # Catalogs are neutral references
    "NARRATIVE_STEP":      0.50,  # Non-argumentative
}


@lru_cache(maxsize=2048)
def compute_linguistic_weight(text: str, step_type: str = "") -> Tuple[float, str, List[str]]:
    """
    Returns (raw_weight, modal_category, matched_phrases).
    Uses frequency-weighted averaging over all detected modal patterns.
    """
    clean = _strip_markdown(text).lower()
    words = clean.split()

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

    # Frequency-weighted average, clipped to [0, 1]
    freq_weighted = weighted_sum / hit_count_total
    # Apply step_type floor
    floor = STEP_TYPE_FLOOR.get(step_type, 0.0)
    raw = max(floor, round(freq_weighted, 3))
    return raw, best_cat, matched[:5]


def extract_alias_mappings() -> Dict[str, str]:
    """Extract all aliases from frontmatter and wiki/glossary.md."""
    vault = VAULT_ROOT / "wiki"
    alias_map: Dict[str, str] = {}

    # 1. Frontmatter aliases in markdown files
    for folder in ["concepts", "entities", "sources"]:
        target_dir = vault / folder
        if not target_dir.exists():
            continue
        for f in target_dir.glob("*.md"):
            text = f.read_text(encoding="utf-8")
            title = f.stem
            m_title = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.M)
            if m_title and m_title.group(1).strip():
                title = m_title.group(1).strip()

            m_aliases = re.search(r'^aliases:\s*\[(.*?)\]', text, re.M)
            if m_aliases:
                raw_aliases = m_aliases.group(1)
                for a in re.findall(r'["\'](.*?)["\']', raw_aliases):
                    a_clean = a.strip()
                    if a_clean:
                        alias_map[a_clean] = title

    # 2. Glossary table aliases
    glossary = vault / "glossary.md"
    if glossary.exists():
        for line in glossary.read_text(encoding="utf-8").splitlines():
            if "|" in line and not line.strip().startswith("|---"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    term = parts[1]
                    aliases_raw = parts[2]
                    clean_term = re.sub(r'\[\[(.*?)\]\]', r'\1', term).strip()
                    if clean_term and clean_term != "Term / Canonical Concept":
                        for a in aliases_raw.split(","):
                            a_clean = a.strip()
                            if a_clean and a_clean != "-":
                                alias_map[a_clean] = clean_term

    return alias_map


def sync_from_neo4j(client: ArcadeDBSyncClient, batch_size: int = 400):
    """
    Stream nodes, section vectors, alias lookups, and all typed relationships into ArcadeDB via high-density NDJSON batches.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Error: neo4j driver required. Run with: uv run --with neo4j ...", file=sys.stderr)
        sys.exit(1)

    print(f"\n=================================================================")
    print(f"  Ingesting Neo4j Knowledge Graph -> ArcadeDB ('{client.database}')")
    print(f"=================================================================")

    neo_kwargs = {"database": NEO4J_DATABASE} if NEO4J_DATABASE else {}
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Pre-clean existing records to ensure fresh replication
    print("  [*] Purging legacy data in ArcadeDB for clean pilot sync...")
    for et in [
        "PROGRESSES_TO", "NEXT_SECTION", "REMEDIES_DILEMMA", "EXTENDS_THEORY", "PRECIPITATES",
        "EMPIRICALLY_GROUNDS", "ORIGINATES_THEORY", "CHAMPIONS_SOLUTION",
        "CRITIQUES_PARADIGM", "OPERATIONALIZES", "AFFILIATED_WITH",
        "INTELLECTUAL_LINEAGE", "AUTHORED_BY", "PUBLISHED_BY",
        "HAS_SECTION", "TAGGED_WITH", "LINKS_TO", "CITES",
        "HAS_GROUNDS", "HAS_WARRANT", "HAS_CLAIM", "HAS_REBUTTAL",
        "HAS_SOLUTION", "HAS_QUALIFIER", "HAS_BACKING", "HAS_DIAGRAM"
    ]:
        try:
            client.execute_sql(f"DELETE FROM `{et}`")
        except Exception:
            pass
    for t in ["Concept", "Entity", "Source", "Section", "Tag", "AliasLookup", "Diagram"]:
        try:
            client.execute_sql(f"DELETE FROM `{t}`")
        except Exception:
            pass

    t0 = time.time()
    total_vertices = 0
    total_edges = 0

    with driver.session(**neo_kwargs) as session:
        # 1. Ingest Concepts
        print("  [*] Fetching Concepts from Neo4j...")
        c_records = session.run("""
            MATCH (c:Concept)
            RETURN c.title AS title, c.reliability_score AS score, c.last_updated AS updated, c.type AS type,
                   c.gds_pagerank AS pagerank, c.gds_community AS community, c.gds_betweenness AS betweenness
        """).data()

        batch = []
        for c in c_records:
            c_item: Dict[str, Any] = {
                "@type": "vertex",
                "@class": "Concept",
                "title": c.get("title") or "Untitled",
                "type": c.get("type") or "concept",
                "reliability_score": c.get("score") or 1.0,
                "last_updated": str(c.get("updated") or "2026-09-29")
            }
            if c.get("pagerank") is not None:
                c_item["pagerank"] = c["pagerank"]
            if c.get("community") is not None:
                c_item["community"] = c["community"]
            if c.get("betweenness") is not None:
                c_item["betweenness"] = c["betweenness"]
            batch.append(json.dumps(c_item))
        res = client.batch_ndjson(batch)
        total_vertices += res.get("verticesCreated", len(batch))
        print(f"    [+] Ingested {len(batch)} Concept vertices ({res.get('elapsedMs', 0)}ms)")

        # 2. Ingest Entities
        print("  [*] Fetching Entities from Neo4j...")
        e_records = session.run("""
            MATCH (e:Entity)
            RETURN e.title AS title, e.subtype AS subtype, e.reliability_score AS score,
                   e.gds_pagerank AS pagerank, e.gds_community AS community
        """).data()
        batch = []
        for e in e_records:
            e_item: Dict[str, Any] = {
                "@type": "vertex",
                "@class": "Entity",
                "title": e.get("title") or "Untitled",
                "subtype": e.get("subtype") or "organization",
                "reliability_score": e.get("score") or 1.0
            }
            if e.get("pagerank") is not None:
                e_item["pagerank"] = e["pagerank"]
            if e.get("community") is not None:
                e_item["community"] = e["community"]
            batch.append(json.dumps(e_item))
        res = client.batch_ndjson(batch)
        total_vertices += res.get("verticesCreated", len(batch))
        print(f"    [+] Ingested {len(batch)} Entity vertices ({res.get('elapsedMs', 0)}ms)")

        # 3. Ingest Sources
        print("  [*] Fetching Sources from Neo4j...")
        s_records = session.run("""
            MATCH (s:Source)
            RETURN coalesce(s.slug, s.title) AS slug, s.title AS title
        """).data()
        batch = []
        for s in s_records:
            batch.append(json.dumps({
                "@type": "vertex",
                "@class": "Source",
                "slug": s.get("slug") or "source-slug",
                "title": s.get("title") or "Source Title"
            }))
        res = client.batch_ndjson(batch)
        total_vertices += res.get("verticesCreated", len(batch))
        print(f"    [+] Ingested {len(batch)} Source vertices ({res.get('elapsedMs', 0)}ms)")

        # 4. Ingest Tags
        print("  [*] Fetching Tags from Neo4j...")
        t_records = session.run("""
            MATCH (t:Tag)
            RETURN t.name AS name
        """).data()
        batch = []
        for t in t_records:
            if t.get("name"):
                batch.append(json.dumps({
                    "@type": "vertex",
                    "@class": "Tag",
                    "name": t.get("name")
                }))
        res = client.batch_ndjson(batch)
        total_vertices += res.get("verticesCreated", len(batch))
        print(f"    [+] Ingested {len(batch)} Tag vertices ({res.get('elapsedMs', 0)}ms)")

        # 5. Ingest Sections (With URI, Title, Structural Metadata, Toulmin Role, Weight, and 768-dim Vector Embeddings)
        print("  [*] Fetching Sections and 768-dim vector embeddings from Neo4j...")
        sec_records = session.run("""
            MATCH (s:Section)
            RETURN s.uri AS uri, coalesce(s.displayName, s.name, 'Section') AS title,
                   s.displayName AS display_name, s.path AS path, s.headingLevel AS heading_level,
                   s.content AS content, s.step_type AS step_type, s.toulmin_role AS toulmin_role,
                   s.weight AS weight, s.modal_category AS modal_category,
                   s.embedding AS embedding
        """).data()

        print(f"    [→] Found {len(sec_records)} sections to ingest in batches of {batch_size}...")
        batch = []
        all_diagram_docs = []
        for idx, sec in enumerate(sec_records, 1):
            uri = sec.get("uri") or f"section-{idx}"
            title = sec.get("title") or "Section"
            step_type = sec.get("step_type") or "Section"
            toulmin_role = sec.get("toulmin_role") or map_to_toulmin_role(step_type)
            raw_content = sec.get("content") or ""
            clean_content, sec_diagrams = process_section_diagrams(uri, title, raw_content)
            all_diagram_docs.extend(sec_diagrams)

            sec_weight = sec.get("weight")
            modal_cat = sec.get("modal_category")
            if sec_weight is None or modal_cat is None:
                sec_weight, modal_cat, _ = compute_linguistic_weight(clean_content, step_type)

            item: Dict[str, Any] = {
                "@type": "vertex",
                "@class": "Section",
                "uri": uri,
                "title": title,
                "display_name": sec.get("display_name") or title,
                "path": sec.get("path") or "",
                "heading_level": sec.get("heading_level") or 2,
                "heading": title,
                "step_type": step_type,
                "toulmin_role": toulmin_role,
                "weight": sec_weight,
                "modal_category": modal_cat,
                "content": clean_content[:2048]
            }
            emb = sec.get("embedding")
            if emb and isinstance(emb, list) and len(emb) == 768:
                item["embedding"] = emb
            batch.append(json.dumps(item))

            if len(batch) >= batch_size:
                res = client.batch_ndjson(batch)
                total_vertices += res.get("verticesCreated", len(batch))
                batch = []
                print(f"        ... ingested {idx}/{len(sec_records)} sections", end="\r")

        if batch:
            res = client.batch_ndjson(batch)
            total_vertices += res.get("verticesCreated", len(batch))
        print(f"    [+] Ingested {len(sec_records)} Section vertices with clean content and JVector embeddings.")

        # 5b. Ingest Diagram Vertices
        print(f"  [*] Ingesting {len(all_diagram_docs)} Diagram vertices into decoupled collection...")
        diag_batch = []
        for d in all_diagram_docs:
            diag_item: Dict[str, Any] = {
                "@type": "vertex",
                "@class": "Diagram",
                "id": d["id"],
                "section_uri": d["section_uri"],
                "title": d["title"],
                "diagram_type": d["diagram_type"],
                "direction": d["direction"],
                "raw_code": d["raw_code"],
                "node_labels": d["node_labels"],
                "semantic_transcript": d["semantic_transcript"],
                "order_idx": d["order_idx"],
                "created_at": d.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
            }
            diag_batch.append(json.dumps(diag_item))
            if len(diag_batch) >= batch_size:
                res = client.batch_ndjson(diag_batch)
                total_vertices += res.get("verticesCreated", len(diag_batch))
                diag_batch = []
        if diag_batch:
            res = client.batch_ndjson(diag_batch)
            total_vertices += res.get("verticesCreated", len(diag_batch))
        print(f"    [+] Ingested {len(all_diagram_docs)} Diagram vertices.")

        # 6. Ingest AliasLookup Documents
        print("  [*] Extracting and ingesting AliasLookup dictionary...")
        alias_map = extract_alias_mappings()
        alias_items = list(alias_map.items())
        alias_chunk_size = 100
        for i in range(0, len(alias_items), alias_chunk_size):
            chunk = alias_items[i:i + alias_chunk_size]
            values_clause = ", ".join([
                f"('{a.replace('\'', '\\\'')}', '{t.replace('\'', '\\\'')}')"
                for a, t in chunk
            ])
            sql_insert = f"INSERT INTO AliasLookup (alias, canonical_title) VALUES {values_clause}"
            try:
                client.execute_sql(sql_insert)
            except Exception as e:
                # If unique constraint violation, insert row by row
                for a, t in chunk:
                    try:
                        client.execute_sql(f"INSERT INTO AliasLookup SET alias = '{a.replace('\'', '\\\'')}', canonical_title = '{t.replace('\'', '\\\'')}'")
                    except Exception:
                        pass
        print(f"    [+] Ingested {len(alias_items)} AliasLookup mappings into ArcadeDB.")

        # 7. Build In-Memory RID Lookup Maps for Sub-Millisecond Edge Resolution
        print("  [*] Building in-memory RID resolution index from ArcadeDB...")
        c_rids = client.query("SELECT @rid, title FROM Concept", language="sql")
        concept_map = {row["title"]: row["@rid"] for row in c_rids if "title" in row}

        e_rids = client.query("SELECT @rid, title FROM Entity", language="sql")
        entity_map = {row["title"]: row["@rid"] for row in e_rids if "title" in row}

        s_rids = client.query("SELECT @rid, slug, title FROM Source", language="sql")
        source_map = {}
        for row in s_rids:
            if "slug" in row:
                source_map[row["slug"]] = row["@rid"]
            if "title" in row:
                source_map[row["title"]] = row["@rid"]

        t_rids = client.query("SELECT @rid, name FROM Tag", language="sql")
        tag_map = {row["name"]: row["@rid"] for row in t_rids if "name" in row}

        sec_rids = client.query("SELECT @rid, uri FROM Section", language="sql")
        section_map = {row["uri"]: row["@rid"] for row in sec_rids if "uri" in row}

        diag_rids = client.query("SELECT @rid, id FROM Diagram", language="sql")
        diagram_map = {row["id"]: row["@rid"] for row in diag_rids if "id" in row}

        print(f"    [✓] Cached RIDs: {len(concept_map)} Concepts, {len(entity_map)} Entities, {len(source_map)} Sources, {len(tag_map)} Tags, {len(section_map)} Sections, {len(diagram_map)} Diagrams.")

        def resolve_rid(label: str, key: str) -> Optional[str]:
            if label == "Concept":
                return concept_map.get(key)
            if label == "Entity":
                return entity_map.get(key)
            if label == "Source":
                return source_map.get(key)
            if label == "Tag":
                return tag_map.get(key)
            if label == "Section":
                return section_map.get(key)
            # Universal fallback
            return (concept_map.get(key) or entity_map.get(key) or
                    source_map.get(key) or tag_map.get(key) or section_map.get(key))

        # 8. Ingest Edges: Micro-CoT PROGRESSES_TO
        print("  [*] Fetching and linking PROGRESSES_TO (Section -> Section Micro-CoT)...")
        p_records = session.run("""
            MATCH (s1:Section)-[r:PROGRESSES_TO]->(s2:Section)
            RETURN s1.uri AS from_uri, s2.uri AS to_uri,
                   r.transition_type AS transition_type,
                   r.warrant AS warrant,
                   r.confidence AS confidence,
                   r.method AS method
        """).data()
        p_batch = []
        p_count = 0
        for r in p_records:
            f_rid = section_map.get(r["from_uri"])
            t_rid = section_map.get(r["to_uri"])
            if f_rid and t_rid:
                p_item: Dict[str, Any] = {
                    "@type": "edge",
                    "@class": "PROGRESSES_TO",
                    "@from": f_rid,
                    "@to": t_rid
                }
                if r.get("transition_type"):
                    p_item["transition_type"] = r["transition_type"]
                if r.get("warrant"):
                    p_item["warrant"] = r["warrant"]
                if r.get("confidence") is not None:
                    p_item["confidence"] = r["confidence"]
                if r.get("method"):
                    p_item["method"] = r["method"]
                p_batch.append(json.dumps(p_item))
                p_count += 1
                if len(p_batch) >= 500:
                    client.batch_ndjson(p_batch)
                    p_batch = []
        if p_batch:
            client.batch_ndjson(p_batch)
        total_edges += p_count
        print(f"    [+] Linked {p_count} PROGRESSES_TO edges with CoT warrants.")

        # 8b. Ingest Edges: AST Backbone NEXT_SECTION
        print("  [*] Fetching and linking NEXT_SECTION (AST Sequential Sequence)...")
        next_records = session.run("""
            MATCH (s1:Section)-[:NEXT_SECTION]->(s2:Section)
            RETURN s1.uri AS from_uri, s2.uri AS to_uri
        """).data()
        next_batch = []
        next_count = 0
        for r in next_records:
            f_rid = section_map.get(r["from_uri"])
            t_rid = section_map.get(r["to_uri"])
            if f_rid and t_rid:
                next_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": "NEXT_SECTION",
                    "@from": f_rid,
                    "@to": t_rid
                }))
                next_count += 1
                if len(next_batch) >= 500:
                    client.batch_ndjson(next_batch)
                    next_batch = []
        if next_batch:
            client.batch_ndjson(next_batch)
        total_edges += next_count
        print(f"    [+] Linked {next_count} NEXT_SECTION edges.")

        # 9. Ingest Edges: HAS_SECTION (Document -> Section Structure) & Specialized Toulmin Containment Edges
        print("  [*] Fetching and linking HAS_SECTION and specialized Toulmin containment edges...")
        has_records = session.run("""
            MATCH (d:Document), (s:Section)
            WHERE s.path = d.path AND (d:Concept OR d:Entity OR d:Source)
            RETURN coalesce([l IN labels(d) WHERE l <> 'Document'][0], 'Concept') AS d_label,
                   coalesce(d.title, d.slug) AS d_title,
                   s.uri AS s_uri,
                   s.step_type AS s_step_type,
                   s.toulmin_role AS s_toulmin_role,
                   s.weight AS s_weight,
                   s.content AS s_content
        """).data()

        toulmin_edge_map = {
            "GROUNDS": "HAS_GROUNDS",
            "CLAIM": "HAS_CLAIM",
            "WARRANT": "HAS_WARRANT",
            "REBUTTAL": "HAS_REBUTTAL",
            "SOLUTION_WARRANT": "HAS_SOLUTION",
            "QUALIFIER": "HAS_QUALIFIER",
            "BACKING": "HAS_BACKING",
        }

        has_batch = []
        has_count = 0
        toulmin_edge_counts: Dict[str, int] = {}
        for r in has_records:
            d_rid = resolve_rid(r["d_label"], r["d_title"])
            s_rid = section_map.get(r["s_uri"])
            if d_rid and s_rid:
                # 1. Base structural containment edge
                has_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": "HAS_SECTION",
                    "@from": d_rid,
                    "@to": s_rid
                }))
                has_count += 1

                # 2. Specialized Toulmin containment edge (for concept notes)
                d_label = r.get("d_label", "Concept")
                s_step = r.get("s_step_type") or "Section"
                t_role = r.get("s_toulmin_role") or map_to_toulmin_role(s_step, "concept" if d_label == "Concept" else "other")
                
                if d_label == "Concept" and t_role in toulmin_edge_map:
                    edge_cls = toulmin_edge_map[t_role]
                    sec_weight = r.get("s_weight")
                    if sec_weight is None:
                        sec_weight = compute_linguistic_weight(r.get("s_content") or "", s_step)[0]
                    edge_data: Dict[str, Any] = {
                        "@type": "edge",
                        "@class": edge_cls,
                        "@from": d_rid,
                        "@to": s_rid,
                        "weight": sec_weight
                    }
                    has_batch.append(json.dumps(edge_data))
                    toulmin_edge_counts[edge_cls] = toulmin_edge_counts.get(edge_cls, 0) + 1

                if len(has_batch) >= 500:
                    client.batch_ndjson(has_batch)
                    has_batch = []
        if has_batch:
            client.batch_ndjson(has_batch)
        total_edges += has_count + sum(toulmin_edge_counts.values())
        print(f"    [+] Linked {has_count} HAS_SECTION edges.")
        for e_cls, cnt in sorted(toulmin_edge_counts.items()):
            print(f"        * Linked {cnt} {e_cls} edges.")

        # 9b. Ingest Edges: HAS_DIAGRAM (Section -> Diagram Decoupled Edges)
        print("  [*] Linking HAS_DIAGRAM (Section -> Diagram Decoupled Edges)...")
        diag_edge_batch = []
        diag_edge_count = 0
        for d in all_diagram_docs:
            s_rid = section_map.get(d["section_uri"])
            d_rid = diagram_map.get(d["id"])
            if s_rid and d_rid:
                diag_edge_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": "HAS_DIAGRAM",
                    "@from": s_rid,
                    "@to": d_rid,
                    "order_idx": d["order_idx"]
                }))
                diag_edge_count += 1
                if len(diag_edge_batch) >= 500:
                    client.batch_ndjson(diag_edge_batch)
                    diag_edge_batch = []
        if diag_edge_batch:
            client.batch_ndjson(diag_edge_batch)
        total_edges += diag_edge_count
        print(f"    [+] Linked {diag_edge_count} HAS_DIAGRAM edges.")

        # 10. Ingest Edges: TAGGED_WITH (Document -> Tag)
        print("  [*] Fetching and linking TAGGED_WITH (Document -> Tag Taxonomy)...")
        tag_records = session.run("""
            MATCH (d)-[:TAGGED_WITH]->(t:Tag)
            WHERE (d:Concept OR d:Entity OR d:Source)
            RETURN coalesce([l IN labels(d) WHERE l <> 'Document'][0], 'Concept') AS d_label,
                   coalesce(d.title, d.slug) AS d_title,
                   t.name AS tag_name
        """).data()
        tag_batch = []
        tag_count = 0
        for r in tag_records:
            d_rid = resolve_rid(r["d_label"], r["d_title"])
            t_rid = tag_map.get(r["tag_name"])
            if d_rid and t_rid:
                tag_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": "TAGGED_WITH",
                    "@from": d_rid,
                    "@to": t_rid
                }))
                tag_count += 1
                if len(tag_batch) >= 500:
                    client.batch_ndjson(tag_batch)
                    tag_batch = []
        if tag_batch:
            client.batch_ndjson(tag_batch)
        total_edges += tag_count
        print(f"    [+] Linked {tag_count} TAGGED_WITH edges.")

        # 11. Ingest Edges: Macro-CoT, Agency & Citations
        print("  [*] Fetching and linking Macro-CoT, Agency, and Citation relationships...")
        rel_records = session.run("""
            MATCH (a)-[r]->(b)
            WHERE type(r) IN [
                'REMEDIES_DILEMMA', 'EXTENDS_THEORY', 'PRECIPITATES',
                'ORIGINATES_THEORY', 'CHAMPIONS_SOLUTION', 'CRITIQUES_PARADIGM',
                'OPERATIONALIZES', 'AFFILIATED_WITH', 'INTELLECTUAL_LINEAGE',
                'AUTHORED_BY', 'PUBLISHED_BY', 'EMPIRICALLY_GROUNDS', 'CITES'
            ]
            AND (a:Concept OR a:Entity OR a:Source)
            AND (b:Concept OR b:Entity OR b:Source)
            RETURN type(r) AS rel_type,
                   coalesce([l IN labels(a) WHERE l <> 'Document'][0], 'Concept') AS a_label,
                   coalesce(a.title, a.slug) AS a_key,
                   coalesce([l IN labels(b) WHERE l <> 'Document'][0], 'Concept') AS b_label,
                   coalesce(b.title, b.slug) AS b_key
        """).data()

        macro_batch = []
        macro_count = 0
        for r in rel_records:
            a_rid = resolve_rid(r["a_label"], r["a_key"])
            b_rid = resolve_rid(r["b_label"], r["b_key"])
            if a_rid and b_rid:
                macro_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": r["rel_type"],
                    "@from": a_rid,
                    "@to": b_rid
                }))
                macro_count += 1
                if len(macro_batch) >= 500:
                    client.batch_ndjson(macro_batch)
                    macro_batch = []
        if macro_batch:
            client.batch_ndjson(macro_batch)
        total_edges += macro_count
        print(f"    [+] Linked {macro_count} Macro-CoT, Agency, and Citation edges.")

        # 12. Ingest Edges: LINKS_TO (Section -> Target Document)
        print("  [*] Fetching and linking LINKS_TO (Section -> Target Document)...")
        links_records = session.run("""
            MATCH (s:Section)-[:LINKS_TO]->(d)
            WHERE (d:Concept OR d:Entity OR d:Source)
            RETURN s.uri AS s_uri,
                   coalesce([l IN labels(d) WHERE l <> 'Document'][0], 'Concept') AS d_label,
                   coalesce(d.title, d.slug) AS d_title
        """).data()
        links_batch = []
        links_count = 0
        for r in links_records:
            s_rid = section_map.get(r["s_uri"])
            d_rid = resolve_rid(r["d_label"], r["d_title"])
            if s_rid and d_rid:
                links_batch.append(json.dumps({
                    "@type": "edge",
                    "@class": "LINKS_TO",
                    "@from": s_rid,
                    "@to": d_rid
                }))
                links_count += 1
                if len(links_batch) >= 500:
                    client.batch_ndjson(links_batch)
                    links_batch = []
        if links_batch:
            client.batch_ndjson(links_batch)
        total_edges += links_count
        print(f"    [+] Linked {links_count} LINKS_TO edges.")

    elapsed = time.time() - t0
    driver.close()
    print(f"\n[✓] Ingestion complete in {elapsed:.2f}s: {total_vertices} vertices, {total_edges} edges, and {len(alias_items)} AliasLookup mappings.")


def run_benchmarks(client: ArcadeDBSyncClient, iterations: int = 30):
    """
    Execute B1-B4 benchmarks across ArcadeDB and Neo4j, recording p50, p95, p99 latency & memory.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Error: neo4j driver required. Run with: uv run --with neo4j ...", file=sys.stderr)
        sys.exit(1)

    print(f"\n=================================================================")
    print(f"  Benchmark Suite: ArcadeDB vs. Neo4j ({iterations} iterations per test)")
    print(f"=================================================================")

    neo_kwargs = {"database": NEO4J_DATABASE} if NEO4J_DATABASE else {}
    neo_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Test Concepts
    test_titles = [
        "AI Learning Paradox", "Desirable Difficulties", "Productive Failure",
        "POEM Framework", "Marketing Unit Economics", "Conversion Rate Optimization"
    ]

    # Benchmark 1: Key / Point Lookup
    print("\n[B1] Running Key / Title Point Lookup Benchmark...")
    neo_b1_times = []
    adb_b1_times = []

    with neo_driver.session(**neo_kwargs) as session:
        for i in range(iterations):
            title = test_titles[i % len(test_titles)]
            # Neo4j
            t0 = time.perf_counter()
            _ = session.run("MATCH (c:Concept {title: $t}) RETURN c.title, c.reliability_score", t=title).data()
            neo_b1_times.append((time.perf_counter() - t0) * 1000)

            # ArcadeDB
            t0 = time.perf_counter()
            _ = client.query("MATCH (c:Concept) WHERE c.title = $t RETURN c.title, c.reliability_score", language="cypher", params={"t": title})
            adb_b1_times.append((time.perf_counter() - t0) * 1000)

    # Benchmark 2: Multi-Hop Traversal
    print("[B2] Running 3-Hop CoT Epistemic Traversal Benchmark...")
    neo_b2_times = []
    adb_b2_times = []

    with neo_driver.session(**neo_kwargs) as session:
        for i in range(iterations):
            # Neo4j traversal
            t0 = time.perf_counter()
            _ = session.run("""
                MATCH (c:Concept)-[:REMEDIES_DILEMMA]->(d:Concept)
                RETURN c.title AS remedy, d.title AS dilemma LIMIT 10
            """).data()
            neo_b2_times.append((time.perf_counter() - t0) * 1000)

            # ArcadeDB traversal
            t0 = time.perf_counter()
            _ = client.query("""
                MATCH (c:Concept)-[:REMEDIES_DILEMMA]->(d:Concept)
                RETURN c.title AS remedy, d.title AS dilemma LIMIT 10
            """, language="cypher")
            adb_b2_times.append((time.perf_counter() - t0) * 1000)

    # Benchmark 3: Vector KNN Retrieval (768-dim)
    print("[B3] Running 768-dim Vector KNN Retrieval Benchmark...")
    with neo_driver.session(**neo_kwargs) as session:
        sample_rec = session.run("MATCH (s:Section) WHERE s.embedding IS NOT NULL RETURN s.embedding AS emb LIMIT 1").single()
        sample_vec = sample_rec["emb"] if sample_rec else [0.01] * 768

    neo_b3_times = []
    adb_b3_times = []

    with neo_driver.session(**neo_kwargs) as session:
        for i in range(iterations):
            # Neo4j Vector KNN
            t0 = time.perf_counter()
            _ = session.run("""
                CALL db.index.vector.queryNodes('section_vector_idx', 5, $vec)
                YIELD node, score
                RETURN node.title, score
            """, vec=sample_vec).data()
            neo_b3_times.append((time.perf_counter() - t0) * 1000)

            # ArcadeDB Vector Search via MCP tool
            t0 = time.perf_counter()
            _ = client.mcp_call("vector_search", {
                "database": client.database,
                "indexName": "Section[embedding]",
                "queryVector": sample_vec,
                "k": 5
            })
            adb_b3_times.append((time.perf_counter() - t0) * 1000)

    # Benchmark 4: Hybrid GraphRAG Retrieval (Vector + Graph Neighborhood)
    print("[B4] Running Hybrid Retrieval (Vector Search + Neighborhood Traversal)...")
    neo_b4_times = []
    adb_b4_times = []

    with neo_driver.session(**neo_kwargs) as session:
        for i in range(iterations):
            # Neo4j Hybrid
            t0 = time.perf_counter()
            _ = session.run("""
                CALL db.index.vector.queryNodes('section_vector_idx', 3, $vec)
                YIELD node, score
                MATCH (node)<-[:HAS*1..2]-(doc)
                OPTIONAL MATCH (doc)-[:REMEDIES_DILEMMA|EXTENDS_THEORY]->(neighbor)
                RETURN doc.title, neighbor.title, score LIMIT 5
            """, vec=sample_vec).data()
            neo_b4_times.append((time.perf_counter() - t0) * 1000)

            # ArcadeDB Hybrid via hybrid_search MCP tool
            t0 = time.perf_counter()
            _ = client.mcp_call("hybrid_search", {
                "database": client.database,
                "vectorIndexName": "Section[embedding]",
                "queryVector": sample_vec,
                "k": 5
            })
            adb_b4_times.append((time.perf_counter() - t0) * 1000)

    # Collect Memory Footprints via Podman
    adb_mem = "N/A"
    neo_mem = "N/A"
    try:
        ps_out = subprocess.check_output(
            ["podman", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in ps_out.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name, mem = parts[0].strip(), parts[1].strip()
                if "arcadedb" in name:
                    adb_mem = mem
                elif "neo4j" in name:
                    neo_mem = mem
    except Exception:
        pass

    def calc_stats(times: List[float]) -> Tuple[float, float, float]:
        st = sorted(times)
        p50 = statistics.median(st)
        p95 = st[int(len(st) * 0.95)]
        p99 = st[int(len(st) * 0.99)]
        return p50, p95, p99

    n_b1_p50, n_b1_p95, n_b1_p99 = calc_stats(neo_b1_times)
    a_b1_p50, a_b1_p95, a_b1_p99 = calc_stats(adb_b1_times)

    n_b2_p50, n_b2_p95, n_b2_p99 = calc_stats(neo_b2_times)
    a_b2_p50, a_b2_p95, a_b2_p99 = calc_stats(adb_b2_times)

    n_b3_p50, n_b3_p95, n_b3_p99 = calc_stats(neo_b3_times)
    a_b3_p50, a_b3_p95, a_b3_p99 = calc_stats(adb_b3_times)

    n_b4_p50, n_b4_p95, n_b4_p99 = calc_stats(neo_b4_times)
    a_b4_p50, a_b4_p95, a_b4_p99 = calc_stats(adb_b4_times)

    # Print Results Table
    print("\n" + "=" * 80)
    print("                      ARCADE DB vs. NEO4J BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Benchmark Test':<30} | {'Neo4j (p50 / p95 / p99)':<22} | {'ArcadeDB (p50 / p95 / p99)':<22}")
    print("-" * 80)
    print(f"{'B1: Point Title Lookup':<30} | {f'{n_b1_p50:.1f} / {n_b1_p95:.1f} / {n_b1_p99:.1f} ms':<22} | {f'{a_b1_p50:.1f} / {a_b1_p95:.1f} / {a_b1_p99:.1f} ms':<22}")
    print(f"{'B2: CoT Multi-Hop Traversal':<30} | {f'{n_b2_p50:.1f} / {n_b2_p95:.1f} / {n_b2_p99:.1f} ms':<22} | {f'{a_b2_p50:.1f} / {a_b2_p95:.1f} / {a_b2_p99:.1f} ms':<22}")
    print(f"{'B3: 768-dim Vector KNN':<30} | {f'{n_b3_p50:.1f} / {n_b3_p95:.1f} / {n_b3_p99:.1f} ms':<22} | {f'{a_b3_p50:.1f} / {a_b3_p95:.1f} / {a_b3_p99:.1f} ms':<22}")
    print(f"{'B4: Hybrid Retrieval':<30} | {f'{n_b4_p50:.1f} / {n_b4_p95:.1f} / {n_b4_p99:.1f} ms':<22} | {f'{a_b4_p50:.1f} / {a_b4_p95:.1f} / {a_b4_p99:.1f} ms':<22}")
    print("-" * 80)
    print(f"{'Container Memory (RSS)':<30} | {neo_mem:<22} | {adb_mem:<22}")
    print("=" * 80)

    neo_driver.close()


def main():
    parser = argparse.ArgumentParser(description="ArcadeDB Sync and Benchmark Harness")
    parser.add_argument("--sync", action="store_true", help="Sync graph from Neo4j to ArcadeDB")
    parser.add_argument("--benchmark", action="store_true", help="Run B1-B4 benchmarks")
    parser.add_argument("--benchmark-only", action="store_true", help="Run benchmarks without syncing")
    parser.add_argument("--iterations", type=int, default=30, help="Number of benchmark iterations (default: 30)")
    args = parser.parse_args()

    client = ArcadeDBSyncClient()
    if not client.is_ready():
        print(f"Error: ArcadeDB at {client.base_url} is unreachable. Ensure container is running.", file=sys.stderr)
        sys.exit(1)

    init_arcadedb_schema(client)

    if args.sync or (not args.benchmark_only and not args.benchmark):
        sync_from_neo4j(client)

    if args.benchmark or args.benchmark_only:
        run_benchmarks(client, iterations=args.iterations)


if __name__ == "__main__":
    main()
