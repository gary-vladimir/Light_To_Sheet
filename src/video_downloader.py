"""
Video download functionality for Light to Sheet.

This module handles downloading videos from YouTube using yt_dlp,
with caching support to avoid re-downloading the same video.

Requires:
- yt-dlp >= 2025.11.12
- Deno >= 2.0 (external JS runtime needed by yt-dlp for YouTube)
"""

from __future__ import annotations

import os
import shutil

import yt_dlp


def download_youtube_video(url: str, custom_filename: str | None = None) -> str:
    """Download YouTube video and save locally for reuse.

    Args:
        url: YouTube video URL.
        custom_filename: Optional custom filename (without extension).
                        If None, uses the video ID from the URL.

    Returns:
        Path to the downloaded video file.

    Raises:
        RuntimeError: If Deno is not installed or the download fails.
    """
    _check_deno()
    print(f"Downloading video from: {url}")

    downloads_dir = "downloaded_videos"
    os.makedirs(downloads_dir, exist_ok=True)

    filename = _resolve_filename(url, custom_filename)
    output_path = os.path.join(downloads_dir, f"{filename}.mp4")

    # Return cached file if already downloaded
    if os.path.exists(output_path):
        print(f"Video already downloaded: {output_path}")
        return output_path

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    print(f"Video downloaded and saved to: {output_path}")
    return output_path


def _check_deno() -> None:
    """Verify that Deno is installed (required by yt-dlp for YouTube).

    Raises:
        RuntimeError: If Deno is not found on PATH.
    """
    if shutil.which("deno") is None:
        raise RuntimeError(
            "Deno is required for YouTube downloads. "
            "Install it: brew install deno (macOS) or curl -fsSL https://deno.land/install.sh | sh"
        )


def _resolve_filename(url: str, custom_filename: str | None) -> str:
    """Determine the output filename from a custom name or the URL.

    Args:
        url: YouTube video URL.
        custom_filename: Optional user-provided filename.

    Returns:
        Sanitized filename string (without extension).
    """
    if custom_filename:
        sanitized = "".join(
            c for c in custom_filename if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        return sanitized or "video"

    # Extract video ID from URL
    video_id: str | None = None
    if "youtube.com/watch?v=" in url:
        video_id = url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0]

    return video_id or "video"
