#!/usr/bin/env python3
"""
scripts/arcadedb_client.py
Zero-dependency HTTP & MCP client for interacting with ArcadeDB in Knowledge Lab.
Supports SQL, Cypher, Gremlin, and native MCP queries.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Automatically source .env if present
_env_file = VAULT_ROOT / ".env"
if _env_file.exists():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


class ArcadeDBClient:
    """Zero-dependency client for ArcadeDB REST and MCP HTTP APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("ARCADEDB_URL", "http://localhost:2481")).rstrip("/")
        self.database = database or os.getenv("ARCADEDB_DATABASE", "news")
        self.username = username or os.getenv("ARCADEDB_USER", "root")
        self.password = password or os.getenv("ARCADEDB_PASSWORD", "root_secret")
        self.auth_header = "Basic " + base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        self.timeout = timeout

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ArcadeDB HTTP {e.code}: {err_msg}") from e

    def is_ready(self) -> bool:
        """Check if ArcadeDB server is healthy and ready."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/v1/ready")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def query(
        self,
        command: str,
        language: str = "cypher",
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute an idempotent read query (Cypher, SQL, Gremlin).
        Returns list of result records.
        """
        db = database or self.database
        url = f"{self.base_url}/api/v1/query/{db}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        res = self._post(url, payload)
        return res.get("result", [])

    def execute_command(
        self,
        command: str,
        language: str = "sql",
        params: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a state-modifying write command or DDL statement.
        """
        db = database or self.database
        url = f"{self.base_url}/api/v1/command/{db}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        res = self._post(url, payload)
        return res.get("result", [])

    def batch(
        self,
        operations: List[Dict[str, Any]],
        database: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute atomic multi-operation batch ingestion.
        """
        db = database or self.database
        url = f"{self.base_url}/api/v1/batch/{db}"
        payload = {"operations": operations}
        return self._post(url, payload)

    def mcp_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        request_id: Union[int, str] = 1,
    ) -> Dict[str, Any]:
        """
        Execute an MCP tool call via ArcadeDB's native JSON-RPC endpoint.
        """
        url = f"{self.base_url}/api/v1/mcp"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": request_id,
        }
        return self._post(url, payload)

    def query_cypher(self, command: str, params: Optional[Dict[str, Any]] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience method to execute a Cypher read query."""
        return self.query(command, language="cypher", params=params, database=database)

    def query_sql(self, command: str, params: Optional[Dict[str, Any]] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience method to execute an ArcadeDB SQL read query."""
        return self.query(command, language="sql", params=params, database=database)

    def execute_cypher(self, command: str, params: Optional[Dict[str, Any]] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience method to execute a Cypher write/procedure command."""
        return self.execute_command(command, language="cypher", params=params, database=database)

    def execute_sql(self, command: str, params: Optional[Dict[str, Any]] = None, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience method to execute an ArcadeDB SQL write/DDL command."""
        return self.execute_command(command, language="sql", params=params, database=database)

    def get_types(self, database: Optional[str] = None) -> List[Dict[str, Any]]:
        """Inspect all vertex, edge, and document types in the database."""
        return self.query("SELECT name, type FROM schema:types", language="sql", database=database)


if __name__ == "__main__":
    client = ArcadeDBClient()
    if not client.is_ready():
        print(f"ArcadeDB at {client.base_url} is NOT ready.", file=sys.stderr)
        sys.exit(1)

    print(f"ArcadeDB at {client.base_url} is READY.")
    types = client.get_types()
    print(f"Database '{client.database}' contains {len(types)} schema types:")
    for t in sorted(types, key=lambda x: (x.get('type', ''), x.get('name', ''))):
        print(f"  [{t.get('type', 'unknown').upper()}] {t.get('name')}")
