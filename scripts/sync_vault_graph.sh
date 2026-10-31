#!/usr/bin/env bash
# scripts/sync_vault_graph.sh
# Master post-ingestion synchronization pipeline for the knowledge-lab mono-vault.
# Dynamically branches based on GRAPH_BACKEND (ArcadeDB or Neo4j).

set -e

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$VAULT_ROOT"

if [ -f "$VAULT_ROOT/.env" ]; then
    set -a
    source "$VAULT_ROOT/.env"
    set +a
fi

BACKEND="${GRAPH_BACKEND:-arcadedb}"
BACKEND_UPPER="$(echo "$BACKEND" | tr '[:lower:]' '[:upper:]')"

echo "================================================================="
echo "  Knowledge Lab :: Master Knowledge Graph & Vector Synchronization"
echo "  Active Target Backend : [${BACKEND_UPPER}]"
echo "================================================================="

if [ "$BACKEND" = "arcadedb" ]; then
    echo "  → Mode: Sovereign In-Engine Pipeline (Zero Ollama)"
    echo ""
    echo "[1/5] Auditing Golden Syntheses for Section Epistemic Drift (Pre-Index Sentinel)..."
    python3 scripts/detect_synthesis_deltas.py || true

    echo ""
    echo "[2/5] Synchronizing Vault AST & Dual-Flow CoT Graph to ArcadeDB..."
    python3 scripts/ingest_to_arcadedb.py --purge

    echo ""
    echo "[3/5] Propagating Epistemic Edge Weights & Signed Rebuttals..."
    python3 scripts/recompute_weights.py

    echo ""
    echo "[4/5] Computing In-Engine Graph Analytics (algo.pagerank, algo.betweenness, algo.louvain)..."
    python3 scripts/run_arcadedb_analytics.py

    echo ""
    echo "[5/5] Generating Native In-Engine Embeddings (algo.fastrp) & Updating JVector Index..."
    python3 scripts/embed_arcadedb_native.py

    echo ""
    echo "================================================================="
    echo "  [✓] ArcadeDB Graph, Analytics, Weights, JVector & Deltas Synced!"
    echo "      Zero External Models or Ollama Daemons Invoked."
    echo "================================================================="

else
    echo "  → Mode: Neo4j Pipeline (GDS + Ollama Embeddings)"
    echo ""
    echo "[1/6] Indexing Markdown Vault to Neo4j via ki..."
    ki index wiki

    echo ""
    echo "[2/6] Materializing Graph Schema & Frontmatter Tags..."
    uv run scripts/enrich_graph.py

    echo ""
    echo "[3/6] Extracting Dual-Flow Chain of Thought (Concept CoT)..."
    uv run scripts/extract_dual_flow_cot.py --skip-neural

    echo ""
    echo "[4/6] Extracting Epistemic Entity Arcs & Agency Handshakes (Entity CoT)..."
    uv run scripts/extract_entity_cot.py

    echo ""
    echo "[5/6] Computing Graph Data Science Metrics (GDS)..."
    uv run scripts/run_gds_analytics.py

    echo ""
    echo "[6/6] Updating Section Vector Embeddings via Ollama (nomic-embed-text)..."
    uv run scripts/embed_graph_sections.py

    echo ""
    echo "================================================================="
    echo "  [✓] All Neo4j Graph, Reasoning, GDS, and Vector Planes Synced!"
    echo "================================================================="
fi
