"""
title: Langfuse Observability & Tracing Filter
author: Knowledge Lab
requirements: langfuse, httpx
description: Standalone in-process Open WebUI filter for Langfuse observability. Captures conversational traces, user prompts, assistant generations, latency, and token consumption to Langfuse Cloud or self-hosted instances.
version: 1.0.0
"""

import time
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("langfuse-filter")


class Filter:
    class Valves(BaseModel):
        ENABLE_LANGFUSE: bool = Field(
            default=True,
            description="Enable or disable Langfuse tracing.",
        )
        LANGFUSE_PUBLIC_KEY: str = Field(
            default="",
            description="Langfuse Public Key (pk-lf-...).",
        )
        LANGFUSE_SECRET_KEY: str = Field(
            default="",
            description="Langfuse Secret Key (sk-lf-...).",
        )
        LANGFUSE_HOST: str = Field(
            default="https://cloud.langfuse.com",
            description="Langfuse Host URL (https://cloud.langfuse.com for EU, https://us.cloud.langfuse.com for US).",
        )
        PROJECT_TAG: str = Field(
            default="open-webui",
            description="Default tag attached to all traces.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._langfuse = None
        self._active_generations: Dict[str, Any] = {}

    def _get_langfuse(self):
        if not self.valves.ENABLE_LANGFUSE or Langfuse is None:
            return None
        if not self.valves.LANGFUSE_PUBLIC_KEY or not self.valves.LANGFUSE_SECRET_KEY:
            return None
        if self._langfuse is None:
            try:
                self._langfuse = Langfuse(
                    public_key=self.valves.LANGFUSE_PUBLIC_KEY,
                    secret_key=self.valves.LANGFUSE_SECRET_KEY,
                    host=self.valves.LANGFUSE_HOST,
                )
            except Exception as e:
                logger.warning(f"Error initializing Langfuse client: {e}")
                return None
        return self._langfuse

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Captures prompt before model generation and initializes trace."""
        lf = self._get_langfuse()
        if not lf:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not user_msg:
            return body

        metadata = __metadata__ or {}
        chat_id = metadata.get("chat_id") or metadata.get("session_id") or body.get("chat_id") or body.get("id") or "default_session"
        query_text = user_msg.get("content", "")
        model_name = body.get("model", "unknown")
        user_id = __user__.get("email", "anonymous") if __user__ else "anonymous"

        try:
            gen = lf.start_observation(
                name="chat_turn",
                as_type="generation",
                model=model_name,
                input=query_text,
                metadata={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "tag": self.valves.PROJECT_TAG,
                },
            )
            # Store by both chat_id and latest user message text hash for resilient correlation
            self._active_generations[chat_id] = gen
            if query_text:
                self._active_generations[f"msg_{hash(query_text[:60])}"] = gen
        except Exception as e:
            logger.debug(f"Langfuse inlet error: {e}")

        return body

    def _extract_usage(
        self,
        assistant_msg: Optional[dict],
        body: dict,
        user_msg: Optional[dict] = None,
    ) -> tuple[Optional[dict], Optional[dict]]:
        usage = (assistant_msg.get("usage") if assistant_msg else None) or body.get("usage") or {}
        info = (assistant_msg.get("info") if assistant_msg else None) or {}

        input_tokens = (
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or info.get("prompt_eval_count")
        )
        output_tokens = (
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or info.get("eval_count")
        )
        total_tokens = (
            usage.get("total_tokens")
            or ((int(input_tokens or 0) + int(output_tokens or 0)) if (input_tokens is not None or output_tokens is not None) else None)
        )

        usage_details = None
        if input_tokens is not None or output_tokens is not None:
            usage_details = {
                "input": int(input_tokens or 0),
                "output": int(output_tokens or 0),
                "total": int(total_tokens or 0),
            }
            comp_details = usage.get("completion_tokens_details") or {}
            if "reasoning_tokens" in comp_details and comp_details["reasoning_tokens"]:
                usage_details["reasoning"] = int(comp_details["reasoning_tokens"])
        else:
            u_text = user_msg.get("content", "") if user_msg else ""
            a_text = assistant_msg.get("content", "") if assistant_msg else ""
            if u_text or a_text:
                in_est = max(1, len(u_text.split()) * 4 // 3) if u_text else 0
                out_est = max(1, len(a_text.split()) * 4 // 3) if a_text else 0
                usage_details = {
                    "input": in_est,
                    "output": out_est,
                    "total": in_est + out_est,
                }

        cost_details = None
        cost = usage.get("cost")
        if cost is not None:
            try:
                cost_details = {"total": float(cost)}
            except (ValueError, TypeError):
                pass

        return usage_details, cost_details

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        """Captures assistant response, completion metadata, and flushes trace."""
        lf = self._get_langfuse()
        if not lf:
            return body

        metadata = __metadata__ or {}
        chat_id = metadata.get("chat_id") or metadata.get("session_id") or body.get("chat_id") or body.get("id") or "default_session"

        # Correlate active generation
        gen = self._active_generations.pop(chat_id, None)

        messages = body.get("messages", [])
        user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not gen and user_msg:
            gen = self._active_generations.pop(f"msg_{hash(user_msg.get('content', '')[:60])}", None)

        assistant_msg = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        assistant_content = assistant_msg.get("content", "") if assistant_msg else ""

        usage_details, cost_details = self._extract_usage(assistant_msg, body, user_msg)

        try:
            if gen:
                update_kwargs = {"output": assistant_content[:4000]}
                if usage_details:
                    update_kwargs["usage_details"] = usage_details
                if cost_details:
                    update_kwargs["cost_details"] = cost_details
                gen.update(**update_kwargs)
                gen.end()
            elif assistant_content:
                # Fallback if inlet was bypassed
                standalone_kwargs = {
                    "name": "chat_turn_fallback",
                    "as_type": "generation",
                    "model": body.get("model", "unknown"),
                    "input": user_msg.get("content", "") if user_msg else "",
                    "output": assistant_content[:4000],
                    "metadata": {"chat_id": chat_id},
                }
                if usage_details:
                    standalone_kwargs["usage_details"] = usage_details
                if cost_details:
                    standalone_kwargs["cost_details"] = cost_details
                standalone_gen = lf.start_observation(**standalone_kwargs)
                standalone_gen.end()

            lf.flush()
        except Exception as e:
            logger.debug(f"Langfuse outlet error: {e}")

        return body
