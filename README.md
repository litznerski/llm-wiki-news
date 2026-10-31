# Sovereign LLM-Wiki Boilerplate

A local-first, autonomous knowledge compiler and Socratic learning studio powered by:
- **Obsidian IDE**: Agent-managed markdown knowledge graph.
- **ArcadeDB**: Multi-model graph and vector storage.
- **FastMCP**: Semantic routing and Dual-Flow Chain-of-Thought middleware.
- **Chainlit**: Socratic Learning Studio with live streaming.
- **Astro 5**: High-speed digital garden with Pagefind and interactive Mermaid diagrams.

## Quick Start

1. **Check Prerequisites**:
   ```bash
   ./scripts/check_prerequisites.sh
   ```
2. **Configure Environment**:
   ```bash
   cp setup/.env.example .env
   cp services/fastmcp/.env.example services/fastmcp/.env
   cp services/frontend/.env.example services/frontend/.env
   ```
3. **Install Dependencies**:
   ```bash
   uv sync
   npm --prefix site install
   ```
4. **Start ArcadeDB & Bootstrap Schema**:
   ```bash
   podman compose -f setup/compose.arcadedb.yaml up -d
   uv run scripts/bootstrap_arcadedb.py
   ```
5. **Start Astro Frontend & Chainlit Studio**:
   ```bash
   npm --prefix site run dev
   podman compose -f setup/compose.chainlit.yaml up -d
   ```

See `setup/boilerplate_architecture_and_clean_clone_guide.md` for comprehensive documentation.
