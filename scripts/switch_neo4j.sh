#!/usr/bin/env bash
# scripts/switch_neo4j.sh
# Toggle active Neo4j database between local Podman container and remote Neo4j Aura.
#
# Usage:
#   ./scripts/switch_neo4j.sh aura
#   ./scripts/switch_neo4j.sh podman

set -e

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
MCP_CONFIG="/Users/christoflitznerski/.gemini/config/mcp_config.json"

if [ "$TARGET" = "aura" ]; then
    echo "================================================================="
    echo "  Switching active Neo4j target to: [Neo4j Aura Cloud]"
    echo "================================================================="
    
    # 1. Update .env symlink
    ln -sf .env.aura "$VAULT_ROOT/.env"
    echo "  [✓] Symlinked .env -> .env.aura"
    
    # 2. Update ki vault profile
    if [ -f "$VAULT_ROOT/wiki/.ki/vault.yaml" ]; then
        sed -i '' 's/profile: .*/profile: aura/' "$VAULT_ROOT/wiki/.ki/vault.yaml"
        echo "  [✓] Updated wiki/.ki/vault.yaml to profile: aura"
    fi
    
    # 3. Pause local podman container to conserve RAM
    echo "  → Pausing local neo4j-ki container..."
    podman stop neo4j-ki 2>/dev/null || true
    echo "  [✓] neo4j-ki paused (data preserved in neo4j-ki-data volume)."
    
    # 4. Update Antigravity MCP config if present
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
        echo "  [✓] Updated Antigravity MCP server to Aura."
    fi

    # 5. Update Open WebUI valves in container if running
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
    echo "  Active target is now: Neo4j Aura (neo4j+s://5e683732.databases.neo4j.io)"
    echo "================================================================="

elif [ "$TARGET" = "podman" ]; then
    echo "================================================================="
    echo "  Switching active Neo4j target to: [Local Podman neo4j-ki]"
    echo "================================================================="
    
    # 1. Update .env symlink
    ln -sf .env.local "$VAULT_ROOT/.env"
    echo "  [✓] Symlinked .env -> .env.local"
    
    # 2. Update ki vault profile
    if [ -f "$VAULT_ROOT/wiki/.ki/vault.yaml" ]; then
        sed -i '' 's/profile: .*/profile: default/' "$VAULT_ROOT/wiki/.ki/vault.yaml"
        echo "  [✓] Updated wiki/.ki/vault.yaml to profile: default"
    fi
    
    # 3. Start local podman container
    echo "  → Starting local neo4j-ki container..."
    podman start neo4j-ki 2>/dev/null || true
    echo "  [✓] neo4j-ki started."
    
    # 4. Update Antigravity MCP config if present
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
        echo "  [✓] Updated Antigravity MCP server to local Podman."
    fi

    # 5. Update Open WebUI valves in container if running
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
    echo "  Active target is now: Local Podman (bolt://localhost:7687)"
    echo "================================================================="

else
    echo "Error: Unknown target '$TARGET'"
    echo "Usage: $0 {aura|podman}"
    exit 1
fi
