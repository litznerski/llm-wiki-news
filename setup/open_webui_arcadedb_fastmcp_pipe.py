"""
title: FastMCP Consolidated Retrieval Pipe
author: Knowledge Lab
version: 3.0.0
description: Ultra-thin, zero-logic pass-through pipe connecting OpenWebUI to FastMCP Consolidated Retrieval Flow.
requirements: httpx, pydantic
"""

import os
from typing import Optional, Callable, Awaitable, Dict, Any
from pydantic import BaseModel, Field
import httpx


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority order.")
        fastmcp_url: str = Field(
            default=os.getenv("FASTMCP_URL", "http://fastmcp-middleware:8000"),
            description="FastMCP Middleware base URL.",
        )
        operating_mode: str = Field(
            default="General",
            description="Dialogue mode: 'General' (step-by-step) or 'Learn' (Toulmin Socratic).",
        )
        teachable_agent_mode: bool = Field(
            default=False,
            description="Socratic Gating: Withhold causal warrants and prescriptive solutions.",
        )
        enable_chat_history: bool = Field(
            default=True,
            description="Persist turn interactions in ArcadeDB Key-Store.",
        )
        enable_langfuse: bool = Field(
            default=True,
            description="Emit granular sub-span execution traces to Langfuse.",
        )
        show_status_indicator: bool = Field(
            default=True,
            description="Emit live status chips in the OpenWebUI chat interface.",
        )
        timeout: float = Field(
            default=15.0,
            description="FastMCP HTTP timeout in seconds.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _emit_status(self, emitter, description: str, done: bool = False):
        if emitter and getattr(self.valves, "show_status_indicator", True):
            try:
                await emitter({"type": "status", "data": {"description": description, "done": done}})
            except Exception:
                pass

    def _resolve_base_url(self) -> str:
        base_url = self.valves.fastmcp_url.strip().rstrip("/")
        if base_url.endswith("/inlet"):
            base_url = base_url[:-len("/inlet")].rstrip("/")
        elif base_url.endswith("/api/v1/flow"):
            base_url = base_url[:-len("/api/v1/flow")].rstrip("/")
        return base_url

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not last_user_msg:
            return body

        user_content = last_user_msg.get("content", "").strip()
        chat_id = body.get("chat_id") or (__user__.get("id", "default_chat") if __user__ else "default_chat")

        payload = {
            "chat_id": chat_id,
            "message": user_content,
            "operating_mode": self.valves.operating_mode,
            "teachable_agent_mode": self.valves.teachable_agent_mode,
            "enable_chat_history": self.valves.enable_chat_history,
            "enable_langfuse": self.valves.enable_langfuse,
        }

        base_url = self._resolve_base_url()
        try:
            async with httpx.AsyncClient(timeout=self.valves.timeout) as client:
                res = await client.post(f"{base_url}/api/v1/flow", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    status_msg = data.get("status_message", "Grounded Context Retrieved")
                    injected_prompt = data.get("injected_prompt")

                    await self._emit_status(__event_emitter__, description=status_msg, done=True)
                    if injected_prompt:
                        last_user_msg["content"] = injected_prompt
                else:
                    await self._emit_status(
                        __event_emitter__,
                        description=f"FastMCP HTTP {res.status_code}",
                        done=True,
                    )
        except Exception as e:
            await self._emit_status(
                __event_emitter__,
                description=f"FastMCP Warning: {str(e)[:50]}",
                done=True,
            )

        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        # Pass-through: FastMCP handles turn history recording asynchronously
        messages = body.get("messages", [])
        if not messages:
            return body

        last_assistant_msg = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        if not last_assistant_msg:
            return body

        chat_id = body.get("chat_id") or (__user__.get("id", "default_chat") if __user__ else "default_chat")
        base_url = self._resolve_base_url()
        payload = {
            "chat_id": chat_id,
            "assistant_response": last_assistant_msg.get("content", ""),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{base_url}/api/v1/flow/outlet", json=payload)
        except Exception:
            pass

        return body
