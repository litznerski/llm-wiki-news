#!/usr/bin/env python3
"""
scripts/arcadedb_mcp_bridge.py
Standard I/O (stdio) MCP bridge for ArcadeDB in Knowledge Lab.
Transfers JSON-RPC 2.0 messages between Antigravity/Claude and ArcadeDB's HTTP MCP endpoint.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent

# Sourcing .env
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

ARCADEDB_URL = os.getenv("ARCADEDB_URL", "http://localhost:2481").rstrip("/")
MCP_ENDPOINT = f"{ARCADEDB_URL}/api/v1/mcp"
USERNAME = os.getenv("ARCADEDB_USER", "root")
PASSWORD = os.getenv("ARCADEDB_PASSWORD", "root_secret")
AUTH_HEADER = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()


def handle_message(line: str) -> None:
    line = line.strip()
    if not line:
        return

    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return

    is_notification = "id" not in msg

    req = urllib.request.Request(
        MCP_ENDPOINT,
        data=line.encode("utf-8"),
        headers={
            "Authorization": AUTH_HEADER,
            "Content-Type": "application/json",
            "User-Agent": "antigravity-arcadedb-mcp-bridge/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            data = resp.read().decode("utf-8")
            if not is_notification and data.strip():
                sys.stdout.write(data.strip() + "\n")
                sys.stdout.flush()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if not is_notification:
            err_resp = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"ArcadeDB HTTP {e.code}: {err_body or e.reason}",
                },
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
    except Exception as e:
        if not is_notification:
            err_resp = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Bridge error: {str(e)}",
                },
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


def main():
    # Make executable as stdio server
    for line in sys.stdin:
        handle_message(line)


if __name__ == "__main__":
    main()
