"""
scripts/register_openwebui_arcadedb_model.py
Registers:
1. Function/Filter: 'arcadedb_fastmcp_inlet_filter' from setup/open_webui_arcadedb_fastmcp_pipe.py
2. Model: 'knowledge-arcadedb' linked exclusively to 'arcadedb_fastmcp_inlet_filter'
Preserves:
- 'llama31lates-default' model linked to 'neo4j_hybrid_graphrag_filter'
"""

import sys
import json
import time
import subprocess
from pathlib import Path

FILTER_FILE = Path(__file__).resolve().parent.parent / "setup" / "open_webui_arcadedb_fastmcp_pipe.py"


def register_in_openwebui():
    if not FILTER_FILE.exists():
        print(f"Error: {FILTER_FILE} not found!")
        sys.exit(1)

    with open(FILTER_FILE, "r", encoding="utf-8") as f:
        filter_code = f.read()

    filter_id = "arcadedb_fastmcp_inlet_filter"
    filter_name = "ArcadeDB FastMCP Inlet Filter"
    meta_json = json.dumps({
        "description": "Ultra-thin, zero-logic pass-through pipe connecting OpenWebUI to FastMCP Consolidated Retrieval Flow.",
        "manifest": {
            "title": "FastMCP Consolidated Retrieval Pipe",
            "author": "Knowledge Lab",
            "requirements": "httpx, pydantic",
            "description": "Ultra-thin, zero-logic pass-through pipe connecting OpenWebUI to FastMCP Consolidated Retrieval Flow.",
            "version": "3.0.0"
        },
        "i18n": {}
    })
    valves_json = json.dumps({
        "priority": 0,
        "fastmcp_url": "http://fastmcp-middleware:8000",
        "operating_mode": "General",
        "teachable_agent_mode": False,
        "enable_chat_history": True,
        "enable_langfuse": True,
        "show_status_indicator": True,
        "timeout": 15.0
    })

    model_id = "knowledge-arcadedb"
    model_name = "Karimoo ArcadeDB Assistant"
    base_model = "openrouter/free"
    model_params = json.dumps({
        # "system": (
        #     "You are the ArcadeDB Multi-Model Knowledge Assistant for Knowledge Lab.\n"
        #     "Your responses are grounded in verified graph traversals, Dual-Flow CoT reasoning progressions, "
        #     "and native vector search from the personal knowledge graph.\n\n"
        #     "OPERATIONAL INVARIANTS:\n"
        #     "1. Strict Graph Fidelity: Ground your answers strictly on the verified query results and tabular data provided in the prompt context.\n"
        #     "2. Prescriptive Solutions: When discussing conceptual dilemmas or pathologies, emphasize [:REMEDIES_DILEMMA] counter-architectures.\n"
        #     "3. Wikilink Citations: Always preserve canonical [[Note Title]] wikilinks for concepts and entities in your explanations.\n"
        #     "4. Conciseness: Synthesize the evidence directly without extraneous preamble."
        # ),
        "stream_response": True
    })
    model_meta = json.dumps({
        "profile_image_url": "/static/favicon.png",
        "background_image_url": None,
        "description": "ArcadeDB Grounded Knowledge Assistant leveraging FastMCP Middleware for Multi-Model GraphRAG, OpenCypher 25, and Multi-Model SQL.",
        "capabilities": {
            "file_context": True,
            "vision": False,
            "file_upload": False,
            "web_search": False,
            "image_generation": False,
            "code_interpreter": False,
            "terminal": False,
            "citations": True,
            "status_updates": True,
            "memory": True,
            "builtin_tools": False
        },
        "knowledge": [],
        "tags": ["arcadedb", "fastmcp", "graphrag", "toulmin"],
        "toolIds": [],
        "filterIds": [filter_id]
    })

    # Python script executed inside container
    py_script = f"""
import sqlite3, time, json

con = sqlite3.connect('/app/backend/data/webui.db')
cur = con.cursor()

admin_row = cur.execute("SELECT id FROM user WHERE role='admin' ORDER BY created_at ASC LIMIT 1").fetchone()
admin_id = admin_row[0] if admin_row else 'admin'
now = int(time.time())

# 1. Upsert Filter in 'function' table (merging existing user valves)
existing_row = cur.execute("SELECT valves FROM function WHERE id=?", ({repr(filter_id)},)).fetchone()
if existing_row and existing_row[0]:
    try:
        existing_valves = json.loads(existing_row[0])
        default_valves = json.loads({repr(valves_json)})
        for k, v in default_valves.items():
            if k not in existing_valves:
                existing_valves[k] = v
            elif existing_valves[k] == "" and v != "":
                existing_valves[k] = v
        merged_valves_json = json.dumps(existing_valves)
    except Exception:
        merged_valves_json = {repr(valves_json)}
else:
    merged_valves_json = {repr(valves_json)}

cur.execute('''
INSERT INTO function (id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at)
VALUES (?, ?, ?, 'filter', ?, ?, ?, 1, 0, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name=excluded.name,
    content=excluded.content,
    meta=excluded.meta,
    valves=excluded.valves,
    is_active=1,
    updated_at=excluded.updated_at
''', (
    {repr(filter_id)},
    admin_id,
    {repr(filter_name)},
    {repr(filter_code)},
    {repr(meta_json)},
    merged_valves_json,
    now,
    now
))

# 2. Upsert Model in 'model' table
cur.execute('''
INSERT INTO model (id, user_id, base_model_id, name, params, meta, updated_at, created_at, is_active)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
ON CONFLICT(id) DO UPDATE SET
    name=excluded.name,
    base_model_id=excluded.base_model_id,
    params=excluded.params,
    meta=excluded.meta,
    is_active=1,
    updated_at=excluded.updated_at
''', (
    {repr(model_id)},
    admin_id,
    {repr(base_model)},
    {repr(model_name)},
    {repr(model_params)},
    {repr(model_meta)},
    now,
    now
))

con.commit()

# Verify
f_row = cur.execute("SELECT id, name, is_active, is_global FROM function WHERE id=?", ({repr(filter_id)},)).fetchone()
m_row = cur.execute("SELECT id, name, base_model_id, meta FROM model WHERE id=?", ({repr(model_id)},)).fetchone()
neo4j_m = cur.execute("SELECT id, name, meta FROM model WHERE id='llama31lates-default'").fetchone()

print(f"Registered Filter: {{f_row}}")
print(f"Registered Model: {{m_row[0]}} ({{m_row[1]}} -> base: {{m_row[2]}})")
print(f"Preserved Neo4j Model: {{neo4j_m[0]}} ({{neo4j_m[1]}})")
"""

    cmd = ["podman", "exec", "-i", "open-webui", "python3", "-"]
    proc = subprocess.run(cmd, input=py_script, text=True, capture_output=True)
    if proc.returncode != 0:
        print(f"Error executing registration: {proc.stderr}")
        sys.exit(proc.returncode)
    print(proc.stdout)


if __name__ == "__main__":
    register_in_openwebui()
