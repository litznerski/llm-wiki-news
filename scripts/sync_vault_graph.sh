#!/usr/bin/env bash
# scripts/sync_vault_graph.sh
# Master post-ingestion synchronization pipeline for the knowledge-lab mono-vault.
# Consolidates knowledge graph, Graph OLAP, weights, vectors, and deltas into Sovereign ArcadeDB.

set -e

VAULT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$VAULT_ROOT"

if [ -f "$VAULT_ROOT/.env" ]; then
    set -a
    source "$VAULT_ROOT/.env"
    set +a
fi

echo "================================================================="
echo "  Knowledge Lab :: Sovereign ArcadeDB Knowledge Synchronization"
echo "  Target Backend: ArcadeDB (Port: ${ARCADEDB_URL:-http://localhost:2481}, DB: ${ARCADEDB_DATABASE:-news})"
echo "================================================================="
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
echo "  [✓] Sovereign ArcadeDB Graph, Analytics, Weights & JVector Synced!"
echo "      Zero External Models or Legacy Daemons Invoked."
echo "================================================================="
