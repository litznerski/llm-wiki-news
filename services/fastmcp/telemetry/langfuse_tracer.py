"""
services/fastmcp/telemetry/langfuse_tracer.py
Hierarchical Sub-Span Observability for FastMCP Consolidated Retrieval Flow.
Dispatches nested telemetry traces to Langfuse Cloud when enabled by valve.
Provides zero-overhead (< 0.01ms) no-op execution when disabled.
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional, Iterator
from contextlib import contextmanager

from ..config import settings

logger = logging.getLogger("fastmcp-langfuse")

try:
    from langfuse import Langfuse
    HAS_LANGFUSE = True
except ImportError:
    Langfuse = None
    HAS_LANGFUSE = False


class SpanContext:
    """Wrapper holding mutable output and metadata for a sub-span."""

    def __init__(self, span: Optional[Any] = None):
        self.span = span
        self.output: Optional[Any] = None
        self.metadata: Dict[str, Any] = {}
        self.status_message: Optional[str] = None
        self.level: Optional[str] = None  # "DEFAULT", "WARNING", "ERROR"

    def set_output(self, output: Any) -> None:
        self.output = output

    def add_metadata(self, key: str, val: Any) -> None:
        self.metadata[key] = val

    def update_metadata(self, data: Dict[str, Any]) -> None:
        self.metadata.update(data)


class TurnTraceContext:
    """Execution context for a conversational retrieval turn."""

    def __init__(self, root_span: Optional[Any] = None, tracer: Optional["FastMCPLangfuseTracer"] = None, active: bool = False):
        self.root_span = root_span
        self.tracer = tracer
        self.active = active
        self.output: Optional[Any] = None
        self.metadata: Dict[str, Any] = {}

    @property
    def trace_id(self) -> Optional[str]:
        if self.active and self.root_span and hasattr(self.root_span, "trace_id"):
            return str(self.root_span.trace_id)
        return None

    @contextmanager
    def span(
        self,
        name: str,
        as_type: str = "span",
        input_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[SpanContext]:
        """Creates a nested sub-span under the root turn observation."""
        if not self.active or not self.root_span:
            yield SpanContext(span=None)
            return

        ctx = SpanContext(span=None)
        sub_span = None
        t0 = time.perf_counter()

        try:
            sub_span = self.root_span.start_observation(
                name=name,
                as_type=as_type,
                input=input_data,
                metadata=metadata or {},
            )
            ctx.span = sub_span
        except Exception as e:
            logger.debug(f"Failed to start Langfuse sub-span '{name}': {e}")

        try:
            yield ctx
        except Exception as e:
            ctx.level = "ERROR"
            ctx.status_message = str(e)
            ctx.add_metadata("error", str(e))
            raise
        finally:
            if sub_span:
                try:
                    dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                    ctx.add_metadata("latency_ms", dur_ms)
                    if hasattr(sub_span, "update"):
                        sub_span.update(
                            output=ctx.output,
                            metadata=ctx.metadata,
                            level=ctx.level or "DEFAULT",
                            status_message=ctx.status_message,
                        )
                        sub_span.end()
                    else:
                        sub_span.end(
                            output=ctx.output,
                            metadata=ctx.metadata,
                            level=ctx.level or "DEFAULT",
                            status_message=ctx.status_message,
                        )
                except Exception as e:
                    logger.warning(f"Failed to close Langfuse sub-span '{name}': {e}")


class FastMCPLangfuseTracer:
    """
    Manages Langfuse Cloud trace lifecycle for FastMCP.
    Provides sub-spans:
      - 01_safeguard_classification
      - 02_entity_resolution
      - 03_vector_knn_s0_selection
      - 04_macro_cot_expansion
      - 05_epistemic_json_assembly
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.public_key = public_key if public_key is not None else settings.langfuse_public_key
        self.secret_key = secret_key if secret_key is not None else settings.langfuse_secret_key
        self.host = host if host is not None else settings.langfuse_host
        self.enabled = enabled if enabled is not None else settings.enable_langfuse
        self._client: Optional[Any] = None

    def _get_client(self) -> Optional[Any]:
        if not HAS_LANGFUSE or Langfuse is None:
            return None
        if not self.public_key or not self.secret_key:
            return None

        if self._client is None:
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
                logger.info("Langfuse client initialized successfully for FastMCP.")
            except Exception as e:
                logger.warning(f"Error initializing Langfuse client: {e}")
                self._client = None

        return self._client

    def is_active(self, enable_override: Optional[bool] = None) -> bool:
        """Determines whether Langfuse tracing is active for the current request."""
        flag = enable_override if enable_override is not None else self.enabled
        if not flag or not HAS_LANGFUSE:
            return False
        return self._get_client() is not None

    @contextmanager
    def trace_turn(
        self,
        name: str = "FastMCP_Retrieval_Turn",
        chat_id: Optional[str] = None,
        user_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        enable_override: Optional[bool] = None,
    ) -> Iterator[TurnTraceContext]:
        """
        Wraps an entire FastMCP retrieval turn in a root observation span.
        When inactive, yields a zero-op context.
        """
        if not self.is_active(enable_override):
            yield TurnTraceContext(root_span=None, tracer=self, active=False)
            return

        client = self._get_client()
        if client is None:
            yield TurnTraceContext(root_span=None, tracer=self, active=False)
            return

        root_meta = metadata.copy() if metadata else {}
        if chat_id:
            root_meta["chat_id"] = chat_id

        root_tags = tags or ["fastmcp", "arcadedb", "toulmin-cot"]
        root_span = None
        turn_ctx = TurnTraceContext(root_span=None, tracer=self, active=True)

        try:
            root_span = client.start_observation(
                name=name,
                as_type="chain",
                input=user_prompt,
                metadata=root_meta,
            )
            turn_ctx.root_span = root_span
        except Exception as e:
            logger.debug(f"Failed to start Langfuse root observation: {e}")
            turn_ctx.active = False

        try:
            yield turn_ctx
        except Exception as e:
            turn_ctx.metadata["error"] = str(e)
            raise
        finally:
            if root_span:
                try:
                    if hasattr(root_span, "update"):
                        root_span.update(
                            output=turn_ctx.output,
                            metadata=turn_ctx.metadata,
                        )
                        root_span.end()
                    else:
                        root_span.end(
                            output=turn_ctx.output,
                            metadata=turn_ctx.metadata,
                        )
                    if client and hasattr(client, "flush"):
                        client.flush()
                except Exception as e:
                    logger.warning(f"Failed to flush Langfuse root trace: {e}")


# Singleton instance
tracer = FastMCPLangfuseTracer()
