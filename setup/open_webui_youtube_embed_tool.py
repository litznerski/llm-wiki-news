"""
title: YouTube Video Embed Tool
author: knowledge-lab
author_url: https://github.com/knowledge-lab
version: 1.0.0
description: Embeds an interactive, responsive YouTube video player directly into OpenWebUI chat for learners using OpenWebUI's native Rich UI Element Embedding (HTMLResponse).
requirements: fastapi
"""

import re
from typing import Optional, Tuple
from fastapi.responses import HTMLResponse


class Tools:
    def __init__(self):
        pass

    def embed_youtube_video(
        self,
        video_id_or_url: str,
        title: str = "YouTube Video",
        start_time: Optional[int] = None,
        enable_subtitles: bool = True,
    ) -> Tuple[HTMLResponse, str]:
        """
        Embed an interactive YouTube video player directly inside the OpenWebUI chat interface for the learner.

        :param video_id_or_url: The 11-character YouTube video ID (e.g., 'cijGD1zztJQ') or a full YouTube URL (e.g., 'https://www.youtube.com/watch?v=cijGD1zztJQ').
        :param title: Descriptive title of the video or educational segment.
        :param start_time: Optional start timestamp in seconds.
        :param enable_subtitles: Whether closed captions/subtitles should be automatically loaded (defaults to True).
        :return: An HTMLResponse configured with Content-Disposition inline for OpenWebUI rendering, along with a context summary for the LLM.
        """
        clean_id = self._extract_video_id(video_id_or_url)
        if not clean_id:
            error_html = """
            <div style="padding: 12px; border-radius: 8px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; font-family: sans-serif; font-size: 13px;">
                <strong>Error:</strong> Invalid YouTube Video ID or URL provided.
            </div>
            """
            return (
                HTMLResponse(
                    content=error_html,
                    headers={"Content-Disposition": "inline"},
                ),
                f"Error: Could not extract a valid YouTube video ID from '{video_id_or_url}'.",
            )

        # Build YouTube embed URL with optimal learner parameters
        params = [
            "autoplay=0",
            "rel=0",
            "modestbranding=1",
        ]
        if enable_subtitles:
            params.append("cc_load_policy=1")
        if start_time and start_time > 0:
            params.append(f"start={int(start_time)}")

        param_str = "&".join(params)
        embed_url = f"https://www.youtube.com/embed/{clean_id}?{param_str}"

        # Responsive 16:9 container with sandboxed iframe
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
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .video-container {{
    max-width: 720px;
    margin: 8px 0;
    border-radius: 12px;
    overflow: hidden;
    background: #000000;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
  }}
  .video-header {{
    padding: 8px 14px;
    background: rgba(30, 41, 59, 0.85);
    color: #f1f5f9;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .video-wrapper {{
    position: relative;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
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
      <a href="https://www.youtube.com/watch?v={clean_id}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: none; font-size: 12px;">Watch on YouTube ↗</a>
    </div>
    <div class="video-wrapper">
      <iframe
        src="{embed_url}"
        title="{title}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
        loading="lazy"
      ></iframe>
    </div>
  </div>
</body>
</html>"""

        headers = {"Content-Disposition": "inline"}
        response = HTMLResponse(content=html_content, headers=headers)
        context = f"Successfully embedded YouTube video '{title}' (ID: {clean_id}) into the chat interface for the learner."
        return (response, context)

    def _extract_video_id(self, input_str: str) -> Optional[str]:
        """Extract the 11-character YouTube video ID from a URL or raw ID."""
        input_str = input_str.strip()
        # Direct 11-char ID
        if re.fullmatch(r"^[a-zA-Z0-9_-]{11}$", input_str):
            return input_str

        # Patterns for standard, share, and embed URLs
        patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, input_str)
            if match:
                return match.group(1)

        return None
