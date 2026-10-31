"""
title: Video Testing Pipe
author: knowledge-lab
author_url: https://github.com/knowledge-lab
version: 1.0.0
description: Custom Pipe for Video Testing. Displays an instant video embed from the initial screen prompt suggestion without triggering the LLM, and delegates follow-up chat to the base LLM.
requirements: pydantic, aiohttp
"""

import re
from typing import Optional, Callable, Awaitable, Union, Generator, Iterator
import aiohttp
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        video_id: str = Field(
            default="cijGD1zztJQ",
            description="YouTube video ID to embed.",
        )
        video_title: str = Field(
            default="The Zipper",
            description="Title of the video.",
        )
        enable_subtitles: bool = Field(
            default=True,
            description="Enable closed captions/subtitles by default (cc_load_policy=1).",
        )
        base_model: str = Field(
            default="llama3.1:latest",
            description="Base model to call for normal conversational turns.",
        )
        ollama_url: str = Field(
            default="http://host.containers.internal:11434",
            description="Ollama host URL for conversational turns.",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        return [
            {
                "id": "video_testing_pipe",
                "name": "Video Testing Pipe",
            }
        ]

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> Union[str, Generator, Iterator]:
        messages = body.get("messages", [])
        if not messages:
            return "No messages received."

        last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        user_text = last_user_msg.get("content", "").strip() if last_user_msg else ""

        # =========================================================================
        # 1. INSTANT INTERCEPTION: Initial Screen Chip / Start Video Click
        # Zero LLM call, Zero latency, Zero tokens!
        # =========================================================================
        if self._is_video_trigger(user_text):
            vid = self.valves.video_id
            title = self.valves.video_title
            player_html = self._build_player_html(vid, title)

            # Emit Rich UI Embed (renders the interactive 16:9 iframe inside chat)
            if __event_emitter__:
                try:
                    await __event_emitter__({
                        "type": "embeds",
                        "data": {
                            "html": player_html,
                        },
                    })
                except Exception:
                    pass

                # Emit reflection follow-up chips
                try:
                    await __event_emitter__({
                        "type": "chat:message:follow_ups",
                        "data": {
                            "follow_ups": [
                                f"📝 What are the core principles of {title}?",
                                f"❓ Quiz me on {title}",
                            ],
                        },
                    })
                except Exception:
                    pass

            # Instant markdown response
            return (
                f"### 🎬 Now Playing: {title}\n\n"
                f"The interactive video player has been loaded above with subtitles enabled.\n\n"
                f"*If your browser restricts inline embeds, you can also launch directly:*\n"
                f"[![{title}](https://img.youtube.com/vi/{vid}/hqdefault.jpg)](https://www.youtube.com/watch?v={vid})\n\n"
                f"▶ **[Open '{title}' in YouTube ↗](https://www.youtube.com/watch?v={vid})**"
            )

        # =========================================================================
        # 2. Conversational Turns: Forward to Base LLM
        # =========================================================================
        return await self._call_base_llm(messages)

    def _is_video_trigger(self, text: str) -> bool:
        """Determines if the prompt came from the starter chip or video request."""
        t = text.lower()
        return (
            "start video" in t
            or "play video" in t
            or "the zipper" in t
            or t.startswith("▶")
            or "cijgd1zztjq" in t
        )

    def _build_player_html(self, video_id: str, title: str) -> str:
        """Builds responsive 16:9 sandboxed YouTube embed HTML."""
        sub_param = "&cc_load_policy=1" if self.valves.enable_subtitles else ""
        embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1{sub_param}&rel=0&modestbranding=1"

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    margin: 0;
    padding: 0;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  .video-container {{
    max-width: 720px;
    margin: 4px 0;
    border-radius: 12px;
    overflow: hidden;
    background: #09090b;
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  }}
  .video-header {{
    padding: 10px 14px;
    background: rgba(24, 24, 27, 0.95);
    color: #f4f4f5;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .video-wrapper {{
    position: relative;
    padding-bottom: 56.25%; /* 16:9 Aspect Ratio */
    height: 0;
    overflow: hidden;
  }}
  .video-wrapper iframe {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: 0;
  }}
</style>
</head>
<body>
  <div class="video-container">
    <div class="video-header">
      <span>🎬 {title}</span>
      <a href="https://www.youtube.com/watch?v={video_id}" target="_blank" rel="noopener noreferrer" style="color: #60a5fa; text-decoration: none; font-size: 12px;">Watch on YouTube ↗</a>
    </div>
    <div class="video-wrapper">
      <iframe
        src="{embed_url}"
        title="{title}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>
  </div>
</body>
</html>"""

    async def _call_base_llm(self, messages: list) -> str:
        """Calls base Ollama model for regular chat messages."""
        endpoint = f"{self.valves.ollama_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.valves.base_model,
            "messages": messages,
            "stream": False,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "No content returned.")
                    return f"Error contacting Ollama ({resp.status}): {await resp.text()}"
        except Exception as e:
            return f"Ollama connection error: {e}"
