"""
Video download functionality for Light to Sheet.

This module handles downloading videos from YouTube using yt_dlp,
with caching support to avoid re-downloading the same video.

Requires:
- yt-dlp >= 2025.11.12
- Deno >= 2.0 (external JS runtime needed by yt-dlp for YouTube)

Cookie authentication:
  YouTube blocks downloads from cloud server IPs (bot detection).
  To fix this, provide a Netscape-format cookies.txt file via either:
    1. YOUTUBE_COOKIES_FILE env var pointing to the file path, OR
    2. Place a file at /secrets/youtube_cookies/cookies.txt
       (the default mount point for Cloud Run secrets)
"""

from __future__ import annotations

import logging
import os
import shutil

import yt_dlp

log = logging.getLogger(__name__)

# Paths to look for a YouTube cookies file (checked in order).
_COOKIES_PATHS = [
    os.environ.get("YOUTUBE_COOKIES_FILE", ""),
    "/secrets/youtube_cookies/cookies.txt",
    "cookies.txt",  # local dev convenience
]


def _find_cookies_file() -> str | None:
    """Return the first existing cookies file path, or None."""
    for path in _COOKIES_PATHS:
        if path and os.path.isfile(path):
            log.info("Using YouTube cookies file: %s", path)
            return path
    return None


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

    # Attach cookies file if available (required on cloud servers)
    cookies_file = _find_cookies_file()
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
    else:
        log.warning(
            "No YouTube cookies file found. Downloads may fail on cloud servers. "
            "See DEPLOYMENT.md § 'YouTube Cookies Setup' for instructions."
        )

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
