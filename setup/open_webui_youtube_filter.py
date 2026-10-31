"""
title: YouTube Video Follow-Up Chip Filter
author: knowledge-lab
author_url: https://github.com/knowledge-lab
version: 1.0.0
description: Automatically adds a native OpenWebUI follow-up chip ([▶ Start Video: The Zipper]) below assistant messages, and intercepts the click to render the video player card.
requirements: pydantic
"""

from typing import Optional, Callable, Awaitable
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority")
        video_id: str = Field(default="cijGD1zztJQ", description="YouTube Video ID")
        video_title: str = Field(default="The Zipper", description="Video Title")
        auto_suggest_chip: bool = Field(
            default=True,
            description="Whether to automatically attach the [Start Video] chip below responses.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        """
        Intercepts incoming messages. If the user clicked the [▶ Start Video] chip,
        injects instructions to ensure the model responds with the video launch card.
        """
        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if not last_user_msg:
            return body

        content = last_user_msg.get("content", "").strip()

        # Check if the user clicked the Start Video chip
        if "start video" in content.lower() or "play video" in content.lower() or content.startswith("▶"):
            vid = self.valves.video_id
            title = self.valves.video_title

            # Prepend system instruction to render the video player card
            prompt_injection = (
                f"\n\n[SYSTEM DIRECTIVE: The learner clicked the native UI chip to start the video. "
                f"Present the video using the following high-definition responsive player card:\n"
                f"[![{title}](https://img.youtube.com/vi/{vid}/maxresdefault.jpg)](https://www.youtube.com/watch?v={vid})\n"
                f"▶ **[Click to Launch '{title}' Video Player (Subtitles Enabled)](https://www.youtube.com/watch?v={vid})**\n\n"
                f"Provide a 2-sentence synopsis of what the learner should observe in '{title}'.]"
            )
            last_user_msg["content"] = f"{content} {prompt_injection}"

        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        """
        Attaches the native UI Follow-Up Chip below the assistant's message.
        """
        if not self.valves.auto_suggest_chip:
            return body

        messages = body.get("messages", [])
        assistant_msg = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
        if not assistant_msg:
            return body

        content = assistant_msg.get("content", "")

        # If the video was already launched in this message, offer reflection chips
        if "img.youtube.com" in content or "youtube.com/watch" in content:
            chips = [
                f"📝 Summarize key takeaways from {self.valves.video_title}",
                f"❓ Quiz me on {self.valves.video_title}",
            ]
        else:
            # Offer the Native Start Video Chip
            chips = [
                f"▶ Start Video: {self.valves.video_title}",
                f"📖 Read overview before watching",
            ]

        assistant_msg["follow_ups"] = chips

        if __event_emitter__:
            try:
                await __event_emitter__({
                    "type": "chat:message:follow_ups",
                    "data": {"follow_ups": chips},
                })
            except Exception:
                pass

        return body
