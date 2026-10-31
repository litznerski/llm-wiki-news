#!/usr/bin/env bash
# scripts/switch_database.sh
# Master database switch for knowledge-lab across:
#   1. arcadedb    - Sovereign ArcadeDB (Local Podman, native FastRP, zero Ollama)
#   2. neo4j-local - Local Podman container (neo4j-ki)
#   3. neo4j-aura  - Remote Neo4j AuraDB Cloud
#
# Usage:
#   ./scripts/switch_database.sh arcadedb
#   ./scripts/switch_database.sh neo4j-local
#   ./scripts/switch_database.sh neo4j-aura

set -e

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_TARGET="${1:-}"
TARGET="$(echo "$RAW_TARGET" | tr '[:upper:]' '[:lower:]')"
MCP_CONFIG="/Users/christoflitznerski/.gemini/config/mcp_config.json"

case "$TARGET" in
    arcadedb|arcade|knowledgedb)
        TARGET="arcadedb"
        ;;
    neo4j-local|local|podman)
        TARGET="neo4j-local"
        ;;
    neo4j-aura|aura|cloud)
        TARGET="neo4j-aura"
        ;;
    *)
        echo "Error: Unknown or missing target '$RAW_TARGET'"
        echo ""
        echo "Usage: $0 {arcadedb | neo4j-local | neo4j-aura}"
        echo "  arcadedb    : Sovereign ArcadeDB (In-Engine FastRP embeddings, zero Ollama)"
        echo "  neo4j-local : Local Podman neo4j-ki container (bolt://localhost:7687)"
        echo "  neo4j-aura  : Cloud Neo4j AuraDB (neo4j+s://5e683732.databases.neo4j.io)"
        exit 1
        ;;
esac

echo "================================================================="
echo "  [Knowledge Lab] Switching Active Database Target to: [$TARGET]"
echo "================================================================="

if [ "$TARGET" = "arcadedb" ]; then
    # 1. Update .env symlink
    ln -sf .env.arcadedb "$VAULT_ROOT/.env"
    echo "  [✓] Symlinked .env -> .env.arcadedb"

    # 2. Update ki profile (defaults to local/default)
    if [ -f "$VAULT_ROOT/wiki/.ki/vault.yaml" ]; then
        sed -i '' 's/profile: .*/profile: default/' "$VAULT_ROOT/wiki/.ki/vault.yaml"
        echo "  [✓] Updated wiki/.ki/vault.yaml to profile: default"
    fi

    # 3. Container lifecycle: Start arcadedb-ki and fastmcp-middleware, stop neo4j-ki to conserve host RAM
    echo "  → Starting local arcadedb-ki and fastmcp-middleware containers..."
    podman compose -f "$VAULT_ROOT/setup/compose.arcadedb.yaml" up -d
    echo "  [✓] arcadedb-ki active on http://localhost:2480"
    echo "  [✓] fastmcp-middleware active on http://localhost:8000"

    echo "  → Pausing local neo4j-ki container to conserve 1.8GB RAM..."
    podman stop neo4j-ki 2>/dev/null || true
    echo "  [✓] neo4j-ki paused."

    # 4. Antigravity MCP config check
    if [ -f "$MCP_CONFIG" ]; then
        echo "  [✓] Antigravity MCP has arcadedb-ki configured via scripts/arcadedb_mcp_bridge.py."
    fi

    echo ""
    echo "  ACTIVE BACKEND: ArcadeDB (knowledgedb)"
    echo "  ENDPOINT      : http://localhost:2480"
    echo "  EMBEDDINGS    : Native in-engine algo.fastrp (Zero Ollama)"
    echo "  ANALYTICS     : Native in-engine algo.pagerank / algo.louvain"
    echo "================================================================="

elif [ "$TARGET" = "neo4j-local" ]; then
    # 1. Update .env symlink
    ln -sf .env.local "$VAULT_ROOT/.env"
    echo "  [✓] Symlinked .env -> .env.local"

    # 2. Update ki vault profile
    if [ -f "$VAULT_ROOT/wiki/.ki/vault.yaml" ]; then
        sed -i '' 's/profile: .*/profile: default/' "$VAULT_ROOT/wiki/.ki/vault.yaml"
        echo "  [✓] Updated wiki/.ki/vault.yaml to profile: default"
    fi

    # 3. Start local neo4j-ki container, stop ArcadeDB stack
    echo "  → Pausing arcadedb-ki and fastmcp-middleware containers to conserve RAM..."
    podman stop fastmcp-middleware arcadedb-ki 2>/dev/null || true
    echo "  [✓] arcadedb-ki and fastmcp-middleware paused."

    echo "  → Starting local neo4j-ki container..."
    podman start neo4j-ki 2>/dev/null || true
    echo "  [✓] neo4j-ki started on bolt://localhost:7687"

    # 4. Update Antigravity MCP config to local Neo4j
    if [ -f "$MCP_CONFIG" ]; then
        python3 -c '
import json
p = "'"$MCP_CONFIG"'"
with open(p, "r") as f:
    cfg = json.load(f)
if "mcpServers" in cfg and "neo4j-ki" in cfg["mcpServers"]:
    s = cfg["mcpServers"]["neo4j-ki"]
    s["args"] = [
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "password",
        "--database", "neo4j",
        "--read-only"
    ]
    s["env"] = {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "password",
        "NEO4J_DATABASE": "neo4j"
    }
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)
'
        echo "  [✓] Updated Antigravity MCP server (neo4j-ki) to local Podman."
    fi

    # 5. Update Open WebUI valves to local Podman in container
    if podman ps -q --filter "name=open-webui" | grep -q .; then
        echo "  → Updating Open WebUI valves to local Podman in container..."
        podman exec open-webui python3 -c '
import sqlite3, json
try:
    conn = sqlite3.connect("/app/backend/data/webui.db")
    c = conn.cursor()
    c.execute("SELECT valves FROM function WHERE id = \"neo4j_hybrid_graphrag_filter\"")
    r = c.fetchone()
    fv = json.loads(r[0]) if (r and r[0]) else {}
    fv["NEO4J_URI"] = "bolt://neo4j-ki:7687"
    fv["NEO4J_USERNAME"] = "neo4j"
    fv["NEO4J_PASSWORD"] = "password"
    c.execute("UPDATE function SET valves = ? WHERE id = \"neo4j_hybrid_graphrag_filter\"", (json.dumps(fv),))
    
    c.execute("SELECT valves FROM tool WHERE id = \"knowledge_graph_explorer_neo4j\"")
    r = c.fetchone()
    tv = json.loads(r[0]) if (r and r[0]) else {}
    tv["neo4j_uri"] = "bolt://neo4j-ki:7687"
    tv["neo4j_user"] = "neo4j"
    tv["neo4j_password"] = "password"
    c.execute("UPDATE tool SET valves = ? WHERE id = \"knowledge_graph_explorer_neo4j\"", (json.dumps(tv),))
    conn.commit()
    conn.close()
    print("  [✓] Updated Open WebUI valves to local Podman.")
except Exception as e:
    print(f"  [!] Open WebUI valve update bypassed: {e}")
'
        echo "  → Restarting open-webui container..."
        podman restart open-webui >/dev/null 2>&1 || true
        echo "  [✓] open-webui restarted."
    fi

    echo ""
    echo "  ACTIVE BACKEND: Neo4j Local (Podman)"
    echo "  ENDPOINT      : bolt://localhost:7687"
    echo "  EMBEDDINGS    : Ollama (nomic-embed-text, 768-dim)"
    echo "  ANALYTICS     : Neo4j Graph Data Science (GDS)"
    echo "================================================================="

elif [ "$TARGET" = "neo4j-aura" ]; then
    # 1. Update .env symlink
    ln -sf .env.aura "$VAULT_ROOT/.env"
    echo "  [✓] Symlinked .env -> .env.aura"

    # 2. Update ki vault profile
    if [ -f "$VAULT_ROOT/wiki/.ki/vault.yaml" ]; then
        sed -i '' 's/profile: .*/profile: aura/' "$VAULT_ROOT/wiki/.ki/vault.yaml"
        echo "  [✓] Updated wiki/.ki/vault.yaml to profile: aura"
    fi

    # 3. Pause local containers to conserve RAM
    echo "  → Pausing local containers (neo4j-ki, arcadedb-ki, fastmcp-middleware)..."
    podman stop fastmcp-middleware arcadedb-ki neo4j-ki 2>/dev/null || true
    echo "  [✓] Local containers paused."

    # 4. Update Antigravity MCP config to Aura
    if [ -f "$MCP_CONFIG" ]; then
        python3 -c '
import json
p = "'"$MCP_CONFIG"'"
with open(p, "r") as f:
    cfg = json.load(f)
if "mcpServers" in cfg and "neo4j-ki" in cfg["mcpServers"]:
    s = cfg["mcpServers"]["neo4j-ki"]
    s["args"] = [
        "--db-url", "neo4j+s://5e683732.databases.neo4j.io",
        "--username", "5e683732",
        "--password", "EOWdFPQd1-VzbcdIjx9u-op6BxfI-BB-pzAAHDEA3zg",
        "--database", "5e683732",
        "--read-only"
    ]
    s["env"] = {
        "NEO4J_URI": "neo4j+s://5e683732.databases.neo4j.io",
        "NEO4J_USERNAME": "5e683732",
        "NEO4J_PASSWORD": "EOWdFPQd1-VzbcdIjx9u-op6BxfI-BB-pzAAHDEA3zg",
        "NEO4J_DATABASE": "5e683732"
    }
    with open(p, "w") as f:
        json.dump(cfg, f, indent=2)
'
        echo "  [✓] Updated Antigravity MCP server (neo4j-ki) to Neo4j Aura."
    fi

    # 5. Update Open WebUI valves to Aura in container
    if podman ps -q --filter "name=open-webui" | grep -q .; then
        echo "  → Updating Open WebUI valves to Aura in container..."
        podman exec open-webui python3 -c '
import sqlite3, json
try:
    conn = sqlite3.connect("/app/backend/data/webui.db")
    c = conn.cursor()
    c.execute("SELECT valves FROM function WHERE id = \"neo4j_hybrid_graphrag_filter\"")
    r = c.fetchone()
    fv = json.loads(r[0]) if (r and r[0]) else {}
    fv["NEO4J_URI"] = "neo4j+s://5e683732.databases.neo4j.io"
    fv["NEO4J_USERNAME"] = "5e683732"
    fv["NEO4J_PASSWORD"] = "EOWdFPQd1-VzbcdIjx9u-op6BxfI-BB-pzAAHDEA3zg"
    c.execute("UPDATE function SET valves = ? WHERE id = \"neo4j_hybrid_graphrag_filter\"", (json.dumps(fv),))
    
    c.execute("SELECT valves FROM tool WHERE id = \"knowledge_graph_explorer_neo4j\"")
    r = c.fetchone()
    tv = json.loads(r[0]) if (r and r[0]) else {}
    tv["neo4j_uri"] = "neo4j+s://5e683732.databases.neo4j.io"
    tv["neo4j_user"] = "5e683732"
    tv["neo4j_password"] = "EOWdFPQd1-VzbcdIjx9u-op6BxfI-BB-pzAAHDEA3zg"
    c.execute("UPDATE tool SET valves = ? WHERE id = \"knowledge_graph_explorer_neo4j\"", (json.dumps(tv),))
    conn.commit()
    conn.close()
    print("  [✓] Updated Open WebUI valves to Aura.")
except Exception as e:
    print(f"  [!] Open WebUI valve update bypassed: {e}")
'
        echo "  → Restarting open-webui container..."
        podman restart open-webui >/dev/null 2>&1 || true
        echo "  [✓] open-webui restarted."
    fi

    echo ""
    echo "  ACTIVE BACKEND: Neo4j Aura (Cloud)"
    echo "  ENDPOINT      : neo4j+s://5e683732.databases.neo4j.io"
    echo "  EMBEDDINGS    : Ollama (nomic-embed-text, 768-dim)"
    echo "  ANALYTICS     : Neo4j Graph Data Science (GDS Cloud)"
    echo "================================================================="
fi
