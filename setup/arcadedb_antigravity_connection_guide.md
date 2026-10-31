# ArcadeDB Antigravity Integration & Connection Guide

This guide provides the complete setup instructions for connecting **Antigravity** (the agentic AI development environment and CLI) to the local **ArcadeDB** multi-model engine for [[Knowledge Lab]].

---

## 1. Architectural Overview

Antigravity interfaces with ArcadeDB through two complementary pathways:
1. **Native MCP Server (Tool-Calling Gateway)**: Antigravity connects directly to ArcadeDB's built-in Model Context Protocol endpoint (`http://localhost:2480/api/v1/mcp`) via SSE/HTTP or local stdio bridge, exposing schema introspection, Cypher queries, and vector similarity search as native agent tools.
2. **Programmatic Python REST Client (`httpx`)**: Antigravity automation scripts and background pipelines execute high-throughput batch operations, data synchronization, and Graph Data Science queries via ArcadeDB's JSON REST API (`/api/v1/query` and `/api/v1/command`).

```mermaid
flowchart LR
    AG["Antigravity Agent<br/>(Gemini / Claude / GPT)"] -->|"MCP Tool Calls<br/>(read_cypher, get_schema)"| MCP["ArcadeDB Built-in MCP<br/>(POST /api/v1/mcp)"]
    AG -->|"Python Scripts<br/>(sync, bench, graph_analytics)"| REST["ArcadeDB REST API<br/>(POST /api/v1/query)"]
    MCP --> ENGINE["ArcadeDB Engine<br/>(knowledgedb)"]
    REST --> ENGINE
    ENGINE --> GRAPH["Graph Engine<br/>(Cypher / Gremlin)"]
    ENGINE --> VECTOR["JVector Engine<br/>(768-dim HNSW)"]
    ENGINE --> DOC["Document Engine<br/>(JSON & Schemaless)"]
```

---

## 2. Modality A: Antigravity MCP Server Configuration

Antigravity supports Model Context Protocol servers defined either in the machine-global configuration file or via lazy-loaded tool schema declarations.

### Step 1: Global MCP Registration (`mcp_config.json`)

To enable ArcadeDB tools across all Antigravity agent sessions, register the ArcadeDB server in `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "arcadedb-ki": {
      "serverUrl": "http://localhost:2480/api/v1/mcp",
      "headers": {
        "Authorization": "Basic cm9vdDprYXJpbW9vbGFiX3NlY3JldA=="
      }
    }
  }
}
```

> [!NOTE]
> The basic auth header `cm9vdDprYXJpbW9vbGFiX3NlY3JldA==` is the standard Base64 encoding of `root:root_secret`. If anonymous MCP access is enabled or authentication is handled within the MCP session, the header can be omitted.

### Step 2: Lazy-Loaded Tool Declarations

Antigravity supports lazy-loaded MCP tools where JSON schemas are placed in:
`~/.gemini/antigravity-cli/mcp/arcadedb-ki/`

Create this directory and register two essential tool definitions:

#### Tool 1: `read_arcadedb_cypher.json`
```json
{
  "name": "read_arcadedb_cypher",
  "description": "Execute a read Cypher query on the ArcadeDB knowledgedb database.",
  "parameters": {
    "properties": {
      "query": {
        "description": "The Cypher query to execute.",
        "type": "string"
      },
      "params": {
        "additionalProperties": true,
        "default": {},
        "description": "The parameters to pass to the Cypher query.",
        "type": "object"
      }
    },
    "required": [
      "query"
    ],
    "type": "object"
  }
}
```

#### Tool 2: `get_arcadedb_schema.json`
```json
{
  "name": "get_arcadedb_schema",
  "description": "Inspect the types, buckets, properties, and indexes of the ArcadeDB knowledgedb database.",
  "parameters": {
    "properties": {},
    "type": "object"
  }
}
```

When configured, the Antigravity agent will see `arcadedb-ki` listed under `<mcp_servers>` in its system prompt and can execute queries via `call_mcp_tool`.

---

## 3. Modality B: Workspace Python Client (`httpx`)

For automated vault operations, graph synchronization, and analytics, Antigravity uses a lightweight Python client module located at `scripts/arcadedb_client.py`.

### Client Implementation

```python
"""ArcadeDB HTTP client for Antigravity scripts and pipelines."""

import os
from typing import Any, Dict, List, Optional
import httpx


class ArcadeDBClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("ARCADEDB_URL", "http://localhost:2480")).rstrip("/")
        self.database = database or os.getenv("ARCADEDB_DATABASE", "knowledgedb")
        self.username = username or os.getenv("ARCADEDB_USER", "root")
        self.password = password or os.getenv("ARCADEDB_PASSWORD", "root_secret")
        self.auth = (self.username, self.password)
        self.timeout = timeout

    def query(self, query: str, language: str = "cypher", params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute an idempotent read query (Cypher, SQL, Gremlin)."""
        url = f"{self.base_url}/api/v1/query/{self.database}"
        payload = {"command": query, "language": language}
        if params:
            payload["params"] = params

        with httpx.Client(auth=self.auth, timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])

    def command(self, command: str, language: str = "cypher", params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a state-modifying DDL or write command."""
        url = f"{self.base_url}/api/v1/command/{self.database}"
        payload = {"command": command, "language": language}
        if params:
            payload["params"] = params

        with httpx.Client(auth=self.auth, timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])

    def batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute atomic multi-operation batch ingestion."""
        url = f"{self.base_url}/api/v1/batch/{self.database}"
        with httpx.Client(auth=self.auth, timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    def is_ready(self) -> bool:
        """Check if ArcadeDB is ready to accept connections."""
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/v1/ready")
                return resp.status_code in (200, 204)
        except Exception:
            return False
```

---

## 4. Environment Variables Configuration

To ensure seamless execution across local terminal sessions and Antigravity subagents, configure `.env`:

```bash
# ArcadeDB Connection
ARCADEDB_URL=http://localhost:2480
ARCADEDB_DATABASE=knowledgedb
ARCADEDB_USER=root
ARCADEDB_PASSWORD=root_secret
ARCADEDB_MCP_URL=http://localhost:2480/api/v1/mcp

# Active Runtime Selector (neo4j | arcadedb | dual)
GRAPH_RUNTIME=arcadedb
```

---

## 5. Verification & Testing Playbook

### Test 1: Verify Endpoint Connectivity via Bash
Antigravity agents can test the connection in a single command:

```bash
curl -u root:root_secret -X POST http://localhost:2480/api/v1/query/knowledgedb \
  -H "Content-Type: application/json" \
  -d '{"language": "cypher", "command": "MATCH (n) RETURN count(n) AS node_count"}'
```

Expected response:
```json
{
  "result": [
    {
      "node_count": 0
    }
  ]
}
```

### Test 2: Verify MCP Tool Endpoint
Test that the Streamable HTTP MCP server is listening and healthy:

```bash
curl -i -X POST http://localhost:2480/api/v1/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "antigravity-test", "version": "1.0.0"}}, "id": 1}'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {}
    },
    "serverInfo": {
      "name": "ArcadeDB MCP Server",
      "version": "26.x"
    }
  }
}
```

---

## 6. Comparison: Neo4j Bolt vs. ArcadeDB HTTP in Antigravity

| Dimension | Neo4j Connection | ArcadeDB Connection |
| :--- | :--- | :--- |
| **Transport** | TCP Bolt Protocol (`bolt://localhost:7687`) | HTTP/JSON (`http://localhost:2480`) |
| **MCP Integration** | External Node/Python adapter container | **Native built-in endpoint** (`/api/v1/mcp`) |
| **Sandbox Compatibility** | Requires custom binary protocol handler | Standard HTTP REST (works with `curl`, `httpx`, `fetch`) |
| **Query Dialects** | OpenCypher only | OpenCypher, SQL, Gremlin, GraphQL |
| **Batch Latency** | Sequential Cypher `UNWIND` transactions | High-density JSON Batch endpoint (`/api/v1/batch`) |
