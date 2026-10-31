# Sovereign LLM-Wiki (`llm-wiki-news`)

A local-first, autonomous knowledge compiler and Socratic learning studio powered by:
- **Obsidian IDE**: Agent-managed markdown knowledge graph.
- **ArcadeDB (`arcadedb-news`)**: Multi-model graph and vector storage (`http://localhost:2481`).
- **FastMCP (`fastmcp-news`)**: Semantic routing and Dual-Flow Chain-of-Thought middleware (`http://localhost:8001`).
- **Chainlit (`chainlit-news`)**: Socratic Learning Studio with live streaming (`http://localhost:8081`).
- **Astro 5**: High-speed digital garden with Pagefind and interactive Mermaid diagrams (`http://localhost:4322`).

## Service & Port Topology (Side-by-Side Isolation)

Configured with isolated containers, volumes, and network (`wiki-news-net`) to run side-by-side with other LLM-Wiki instances:

| Service | Container Name | Host Port Mapping | Local Endpoint |
| :--- | :--- | :--- | :--- |
| **ArcadeDB Studio / REST / MCP** | `arcadedb-news` | `2481:2480`, `2425:2424` | `http://localhost:2481` |
| **FastMCP Middleware** | `fastmcp-news` | `8001:8000` | `http://localhost:8001` |
| **Chainlit Learning Studio** | `chainlit-news` | `8081:8080` | `http://localhost:8081` |
| **Astro Digital Garden** | *(Host Dev Server)* | `4322` | `http://localhost:4322` |

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
4. **Start ArcadeDB (`arcadedb-news`) & Bootstrap Schema**:
   ```bash
   podman compose -f setup/compose.arcadedb.yaml up -d
   uv run scripts/bootstrap_arcadedb.py
   ```
5. **Start Astro Frontend & Chainlit Studio (`chainlit-news`)**:
   ```bash
   npm --prefix site run dev
   podman compose -f setup/compose.chainlit.yaml up -d
   ```

See `setup/boilerplate_architecture_and_clean_clone_guide.md` for comprehensive documentation.
