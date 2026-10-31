"""
services/fastmcp/arcadedb_client.py
High-performance HTTP client for ArcadeDB built with httpx and standard library fallback.
Interacts with ArcadeDB REST endpoints (/api/v1/query, /api/v1/command, /api/v1/ready).
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    import urllib.request
    import urllib.error
    import asyncio
    HAS_HTTPX = False

from .config import settings

logger = logging.getLogger("fastmcp-arcadedb-client")


class ArcadeDBHttpClient:
    """HTTP client for ArcadeDB query execution and health checking."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.base_url = (base_url or settings.arcadedb_url).rstrip("/")
        self.database = database or settings.arcadedb_database
        self.username = username or settings.arcadedb_user
        self.password = password or settings.arcadedb_password
        self.timeout = timeout
        
        # Precompute Basic Auth header
        auth_bytes = f"{self.username}:{self.password}".encode("utf-8")
        self.auth_header = f"Basic {base64.b64encode(auth_bytes).decode('utf-8')}"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _urllib_post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback POST handler using urllib.request."""
        import urllib.request
        import urllib.error
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ArcadeDB HTTP {e.code}: {err_msg}") from e

    def is_ready(self) -> bool:
        """Checks if the ArcadeDB instance is healthy and ready to accept queries."""
        url = f"{self.base_url}/api/v1/ready"
        if HAS_HTTPX:
            try:
                with httpx.Client(timeout=5.0) as client:
                    res = client.get(url)
                    return res.status_code in (200, 204)
            except Exception:
                return False
        else:
            import urllib.request
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    return resp.status in (200, 204)
            except Exception:
                return False

    async def is_ready_async(self) -> bool:
        """Asynchronously checks if ArcadeDB is healthy."""
        url = f"{self.base_url}/api/v1/ready"
        if HAS_HTTPX:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(url)
                    return res.status_code in (200, 204)
            except Exception:
                return False
        else:
            import asyncio
            return await asyncio.to_thread(self.is_ready)

    def query(
        self,
        command: str,
        language: str = "cypher",
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a read-only query (OpenCypher or ArcadeDB SQL) synchronously.
        Routes to POST /api/v1/query/{database}.
        """
        url = f"{self.base_url}/api/v1/query/{self.database}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._get_headers())
                if res.status_code != 200:
                    raise RuntimeError(f"ArcadeDB query error ({res.status_code}): {res.text}")
                return res.json().get("result", [])
        else:
            res = self._urllib_post(url, payload)
            return res.get("result", [])

    async def query_async(
        self,
        command: str,
        language: str = "cypher",
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a read-only query (OpenCypher or ArcadeDB SQL) asynchronously.
        Routes to POST /api/v1/query/{database}.
        """
        url = f"{self.base_url}/api/v1/query/{self.database}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        if HAS_HTTPX:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=self._get_headers())
                if res.status_code != 200:
                    raise RuntimeError(f"ArcadeDB query error ({res.status_code}): {res.text}")
                return res.json().get("result", [])
        else:
            import asyncio
            res = await asyncio.to_thread(self._urllib_post, url, payload)
            return res.get("result", [])

    def command(
        self,
        command: str,
        language: str = "sql",
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a command or DDL statement synchronously.
        Routes to POST /api/v1/command/{database}.
        """
        url = f"{self.base_url}/api/v1/command/{self.database}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        if HAS_HTTPX:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._get_headers())
                if res.status_code != 200:
                    raise RuntimeError(f"ArcadeDB command error ({res.status_code}): {res.text}")
                return res.json().get("result", [])
        else:
            res = self._urllib_post(url, payload)
            return res.get("result", [])

    async def command_async(
        self,
        command: str,
        language: str = "sql",
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a command or DDL statement asynchronously.
        Routes to POST /api/v1/command/{database}.
        """
        url = f"{self.base_url}/api/v1/command/{self.database}"
        payload: Dict[str, Any] = {"command": command, "language": language}
        if params:
            payload["params"] = params

        if HAS_HTTPX:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=self._get_headers())
                if res.status_code != 200:
                    raise RuntimeError(f"ArcadeDB command error ({res.status_code}): {res.text}")
                return res.json().get("result", [])
        else:
            import asyncio
            res = await asyncio.to_thread(self._urllib_post, url, payload)
            return res.get("result", [])
