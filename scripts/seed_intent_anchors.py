#!/usr/bin/env python3
"""
scripts/seed_intent_anchors.py
Synchronizes ArcadeDB IntentAnchor documents from the human-maintainable
markdown file in setup/safeguard_intent_anchors.md.
Uses 100% native in-engine ArcadeDB execution (Lucene FULL_TEXT + algo.fastrp).
Zero external Ollama or API calls.
"""

import os
import sys
import re
import time
from pathlib import Path
from typing import List, Dict, Any

VAULT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(VAULT_ROOT))

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

from scripts.arcadedb_client import ArcadeDBClient


def parse_intent_catalog(markdown_path: Path) -> List[Dict[str, Any]]:
    """Parses setup/safeguard_intent_anchors.md into a list of anchor record dicts."""
    if not markdown_path.exists():
        raise FileNotFoundError(f"Intent anchors catalog not found at: {markdown_path}")

    with open(markdown_path, "r", encoding="utf-8") as f:
        content = f.read()

    intent_blocks = re.findall(r"### \x60(.*?)\x60\n(.*?)(?=\n### |\Z)", content, re.DOTALL)
    anchors: List[Dict[str, Any]] = []

    for intent, body in intent_blocks:
        cat_m = re.search(r"\- \*\*Category\*\*:\s*\x60?(.*?)\x60?\n", body)
        act_m = re.search(r"\- \*\*Action\*\*:\s*\x60?(.*?)\x60?\n", body)
        tmpl_m = re.search(r"\- \*\*Response Template\*\*:\n(.*?)(?=\n\- \*\*Utterances\*\*:)", body, re.DOTALL)

        category = cat_m.group(1).strip() if cat_m else "unknown"
        action = act_m.group(1).strip() if act_m else "PROCEED"
        template = tmpl_m.group(1).strip() if tmpl_m else ""

        utterances = re.findall(r"^\s*-\s*\"(.*?)\"", body, re.MULTILINE)
        for u in utterances:
            clean_u = u.strip()
            if clean_u:
                anchors.append({
                    "intent": intent,
                    "category": category,
                    "action": action,
                    "utterance": clean_u,
                    "response_template": template,
                })

    return anchors


def seed_intent_anchors():
    print("=" * 65)
    print("  ArcadeDB Native Intent Anchor Seeding (setup/ -> ArcadeDB)")
    print("  Zero External Embedding Dependencies")
    print("=" * 65)

    client = ArcadeDBClient()
    print(f"[*] Connected to ArcadeDB at {client.base_url} (Database: {client.database})")

    # 1. Ensure Schema DDL
    print("[*] Ensuring IntentAnchor Document Type and Indexes exist...")
    ddl_commands = [
        "CREATE DOCUMENT TYPE IntentAnchor IF NOT EXISTS;",
        "CREATE PROPERTY IntentAnchor.intent STRING;",
        "CREATE PROPERTY IntentAnchor.category STRING;",
        "CREATE PROPERTY IntentAnchor.action STRING;",
        "CREATE PROPERTY IntentAnchor.utterance STRING;",
        "CREATE PROPERTY IntentAnchor.response_template STRING;",
        "CREATE PROPERTY IntentAnchor.embedding LIST OF FLOAT;",
        "CREATE INDEX IF NOT EXISTS ON IntentAnchor (intent) NOTUNIQUE;",
        "CREATE INDEX IF NOT EXISTS ON IntentAnchor (category) NOTUNIQUE;",
        "CREATE INDEX IF NOT EXISTS ON IntentAnchor (utterance) FULL_TEXT;",
        'CREATE INDEX IF NOT EXISTS ON IntentAnchor (embedding) LSM_VECTOR METADATA {"dimensions": 768, "similarity": "COSINE"};',
    ]

    for cmd in ddl_commands:
        try:
            client.execute_sql(cmd)
        except Exception as e:
            # Ignore already exists warnings
            if "already exists" not in str(e).lower():
                print(f"  [!] DDL note ({cmd[:35]}...): {e}")

    print("  [✓] DDL and indexes verified.")

    # 2. Parse Markdown File
    catalog_path = VAULT_ROOT / "setup" / "safeguard_intent_anchors.md"
    print(f"[*] Parsing intent anchors from {catalog_path}...")
    anchors = parse_intent_catalog(catalog_path)
    print(f"  [✓] Parsed {len(anchors)} anchor utterances across intents.")

    # 3. Truncate existing anchors for clean sync
    print("[*] Refreshing IntentAnchor documents...")
    try:
        client.execute_sql("DELETE FROM IntentAnchor;")
    except Exception as e:
        print(f"  [!] Delete note: {e}")

    # 4. Insert records
    t0 = time.perf_counter()
    inserted = 0
    for a in anchors:
        insert_sql = """
        INSERT INTO IntentAnchor CONTENT {
            "intent": :intent,
            "category": :category,
            "action": :action,
            "utterance": :utterance,
            "response_template": :response_template
        };
        """
        try:
            client.execute_sql(
                insert_sql,
                params={
                    "intent": a["intent"],
                    "category": a["category"],
                    "action": a["action"],
                    "utterance": a["utterance"],
                    "response_template": a["response_template"],
                },
            )
            inserted += 1
        except Exception as e:
            print(f"  [!] Error inserting utterance '{a['utterance']}': {e}")

    elapsed_insert = (time.perf_counter() - t0) * 1000
    print(f"  [✓] Inserted {inserted} / {len(anchors)} IntentAnchor records in {elapsed_insert:.2f}ms.")

    # 5. In-Engine FastRP Embedding Materialization (Zero Ollama)
    print("[*] Running native in-engine algo.fastrp projection (Zero Ollama)...")
    t1 = time.perf_counter()
    try:
        fastrp_cypher = """
        CALL algo.fastrp({
          dimensions: 768,
          iterations: 4,
          normalization: -0.5,
          selfInfluence: 0.1,
          direction: 'BOTH'
        })
        YIELD node, embedding
        WITH toString(node) AS rid_str, embedding
        MATCH (n) WHERE elementId(n) = rid_str AND n:IntentAnchor
        SET n.embedding = embedding
        RETURN count(n) AS total_embedded;
        """
        res = client.execute_cypher(fastrp_cypher)
        total_embedded = res[0].get("total_embedded", 0) if res else 0
        elapsed_fastrp = (time.perf_counter() - t1) * 1000
        print(f"  [✓] algo.fastrp materialized embeddings in {elapsed_fastrp:.2f}ms.")
    except Exception as e:
        print(f"  [!] algo.fastrp note: {e}")

    # 6. Verification
    verify_res = client.query_sql("SELECT count(*) AS count FROM IntentAnchor;")
    count = verify_res[0].get("count", 0) if verify_res else 0
    print("=" * 65)
    print(f"  Sync Complete: {count} IntentAnchors active in ArcadeDB.")
    print("=" * 65)


if __name__ == "__main__":
    seed_intent_anchors()
