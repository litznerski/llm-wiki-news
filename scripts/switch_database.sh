#!/usr/bin/env bash
# scripts/switch_database.sh
# Sovereign ArcadeDB database lifecycle and verification manager for Knowledge Lab.
# Manages the sovereign ArcadeDB container stack (arcadedb-news & fastmcp-news).
#
# Usage:
#   ./scripts/switch_database.sh [start | stop | status | restart]

set -e

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$VAULT_ROOT"

ACTION="${1:-status}"
ACTION="$(echo "$ACTION" | tr '[:upper:]' '[:lower:]')"

case "$ACTION" in
    arcadedb|start|up)
        echo "================================================================="
        echo "  [Knowledge Lab] Starting Sovereign ArcadeDB Stack"
        echo "================================================================="
        podman compose -f "$VAULT_ROOT/setup/compose.arcadedb.yaml" up -d
        echo "  [✓] arcadedb-news active on http://localhost:2481"
        echo "  [✓] fastmcp-news active on http://localhost:8001"
        ;;
    stop|down)
        echo "================================================================="
        echo "  [Knowledge Lab] Stopping Sovereign ArcadeDB Stack"
        echo "================================================================="
        podman compose -f "$VAULT_ROOT/setup/compose.arcadedb.yaml" down
        echo "  [✓] ArcadeDB stack stopped."
        ;;
    restart)
        echo "================================================================="
        echo "  [Knowledge Lab] Restarting Sovereign ArcadeDB Stack"
        echo "================================================================="
        podman compose -f "$VAULT_ROOT/setup/compose.arcadedb.yaml" restart
        echo "  [✓] ArcadeDB stack restarted."
        ;;
    status|*)
        echo "================================================================="
        echo "  [Knowledge Lab] Sovereign ArcadeDB Engine Status"
        echo "================================================================="
        echo "  Active Backend : ArcadeDB (Multi-Model Engine)"
        echo "  Database       : news"
        echo "  HTTP Endpoint  : http://localhost:2481"
        echo "  Embeddings     : Native In-Engine algo.fastrp (768-dim)"
        echo "  Analytics      : Native In-Engine algo.pagerank / algo.louvain"
        echo "-----------------------------------------------------------------"
        podman ps --filter "name=arcadedb-news" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
        echo "================================================================="
        ;;
esac
