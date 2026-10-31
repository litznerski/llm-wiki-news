"""
services/fastmcp/config.py
Configuration and environment variable management for the FastMCP ArcadeDB Middleware.
Sources settings strictly from .env files or container environments with zero hardcoded clear-text secrets.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    from dataclasses import dataclass, field
    HAS_PYDANTIC = False

# Locate candidate .env files in order of priority:
# 1. Local service directory: services/fastmcp/.env
# 2. Vault root: ../../.env (which symlinks to .env.arcadedb)
_SERVICE_DIR = Path(__file__).resolve().parent
_VAULT_ROOT = _SERVICE_DIR.parent.parent

_CANDIDATE_ENV_PATHS = [
    _SERVICE_DIR / ".env",
    _VAULT_ROOT / ".env",
]


def load_env_file() -> Optional[Path]:
    """Loads environment variables from the first discovered .env file."""
    for env_path in _CANDIDATE_ENV_PATHS:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            # Set if not already present in environment
                            if k and k not in os.environ:
                                os.environ[k] = v
                return env_path
            except Exception:
                pass
    return None


# Load environment variables on module import
ACTIVE_ENV_FILE = load_env_file()


if HAS_PYDANTIC:
    class Settings(BaseModel):
        """Runtime configuration for FastMCP ArcadeDB Middleware (Pydantic)."""
        arcadedb_url: str = Field(
            default_factory=lambda: os.getenv("ARCADEDB_URL", "http://localhost:2480").rstrip("/")
        )
        arcadedb_database: str = Field(
            default_factory=lambda: os.getenv("ARCADEDB_DATABASE", "news")
        )
        arcadedb_user: str = Field(
            default_factory=lambda: os.getenv("ARCADEDB_USER", "root")
        )
        arcadedb_password: str = Field(
            default_factory=lambda: os.getenv("ARCADEDB_PASSWORD", "")
        )
        default_dialect: str = Field(
            default_factory=lambda: os.getenv("DEFAULT_DIALECT", "auto").lower()
        )
        host: str = Field(
            default_factory=lambda: os.getenv("HOST", "0.0.0.0")
        )
        port: int = Field(
            default_factory=lambda: int(os.getenv("PORT", "8000"))
        )
        log_level: str = Field(
            default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
        )
        enable_langfuse: bool = Field(
            default_factory=lambda: os.getenv("ENABLE_LANGFUSE", "false").lower() in ("true", "1", "yes")
        )
        langfuse_public_key: str = Field(
            default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", "")
        )
        langfuse_secret_key: str = Field(
            default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", "")
        )
        langfuse_host: str = Field(
            default_factory=lambda: os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        )
else:
    @dataclass
    class Settings:
        """Runtime configuration for FastMCP ArcadeDB Middleware (Dataclass Fallback)."""
        arcadedb_url: str = field(
            default_factory=lambda: os.getenv("ARCADEDB_URL", "http://localhost:2480").rstrip("/")
        )
        arcadedb_database: str = field(
            default_factory=lambda: os.getenv("ARCADEDB_DATABASE", "news")
        )
        arcadedb_user: str = field(
            default_factory=lambda: os.getenv("ARCADEDB_USER", "root")
        )
        arcadedb_password: str = field(
            default_factory=lambda: os.getenv("ARCADEDB_PASSWORD", "")
        )
        default_dialect: str = field(
            default_factory=lambda: os.getenv("DEFAULT_DIALECT", "auto").lower()
        )
        host: str = field(
            default_factory=lambda: os.getenv("HOST", "0.0.0.0")
        )
        port: int = field(
            default_factory=lambda: int(os.getenv("PORT", "8000"))
        )
        log_level: str = field(
            default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
        )
        enable_langfuse: bool = field(
            default_factory=lambda: os.getenv("ENABLE_LANGFUSE", "false").lower() in ("true", "1", "yes")
        )
        langfuse_public_key: str = field(
            default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", "")
        )
        langfuse_secret_key: str = field(
            default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", "")
        )
        langfuse_host: str = field(
            default_factory=lambda: os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        )


settings = Settings()
