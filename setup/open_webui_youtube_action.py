"""
title: YouTube Video Action
author: knowledge-lab
author_url: https://github.com/knowledge-lab
version: 1.0.0
description: Adds a native UI action chip/button directly to the message toolbar that starts and embeds an interactive YouTube video player upon click.
requirements: fastapi, pydantic
"""

import re
from typing import Optional
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class Action:
    class Valves(BaseModel):
        default_video_id: str = Field(
            default="cijGD1zztJQ",
            description="Default YouTube video ID if none is detected in message prose.",
        )
        default_title: str = Field(
            default="The Zipper",
            description="Default video title.",
        )
        enable_subtitles: bool = Field(
            default=True,
            description="Automatically enable closed captions/subtitles (cc_load_policy=1).",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self,
        body: dict,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
    ) -> HTMLResponse:
        """
        Executes when the user clicks the native UI action chip/button on the message.
        Embeds the responsive 16:9 YouTube video player into the message.
        """
        # 1. Extract message text to detect video ID or URL
        messages = body.get("messages", [])
        last_message_content = ""
        if messages:
            last_message_content = messages[-1].get("content", "")

        video_id, title = self._detect_video_metadata(last_message_content)
        if not video_id:
            video_id = self.valves.default_video_id
        if not title:
            title = self.valves.default_title

        # 2. Build responsive HTML player with inline Content-Disposition
        sub_param = "&cc_load_policy=1" if self.valves.enable_subtitles else ""
        embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1{sub_param}&rel=0&modestbranding=1"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    margin: 0;
    padding: 0;
    background-color: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  .video-container {{
    max-width: 720px;
    margin: 6px 0;
    border-radius: 12px;
    overflow: hidden;
    background: #09090b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
  }}
  .video-header {{
    padding: 10px 14px;
    background: rgba(24, 24, 27, 0.9);
    color: #fafafa;
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
      <span>▶ Now Playing: {title}</span>
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

        return HTMLResponse(
            content=html_content,
            headers={"Content-Disposition": "inline"},
        )

    def _detect_video_metadata(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Scans message text for YouTube video IDs, URLs, or known titles."""
        # Check standard YouTube URLs or direct IDs
        patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"\b([a-zA-Z0-9_-]{11})\b",
        ]
        video_id = None
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                video_id = match.group(1)
                break

        title = None
        if "zipper" in text.lower():
            title = "The Zipper"

        return video_id, title
