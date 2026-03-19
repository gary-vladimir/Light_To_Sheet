"""
Video download functionality for Light to Sheet.

Downloads YouTube videos using one of two strategies:

  1. **Download Proxy** (production) — If DOWNLOAD_PROXY_URL is set, sends
     the URL to an external proxy server running on a residential IP
     (e.g., your Mac via Cloudflare Tunnel).  The proxy downloads the video
     with yt-dlp and streams it back.

  2. **yt-dlp direct** (local dev) — Falls back to downloading directly
     with yt-dlp when no proxy is configured.

See DOWNLOAD_PROXY_SETUP.md for production proxy setup.
"""

from __future__ import annotations

import os
import tempfile
from urllib.parse import urlparse, parse_qs

import requests
import yt_dlp


# --- Configuration ---

_PROXY_URL = os.environ.get("DOWNLOAD_PROXY_URL", "").rstrip("/")
_PROXY_KEY = os.environ.get("PROXY_API_KEY", "")
_PROXY_TIMEOUT = 600  # 10 min — video downloads can be slow


def download_youtube_video(url: str, custom_filename: str | None = None) -> str:
    """Download a YouTube video and return the local file path.

    Uses the download proxy in production, yt-dlp directly in local dev.
    Results are cached — the same URL won't be downloaded twice.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise RuntimeError(f"Could not extract video ID from: {url}")

    downloads_dir = os.path.join(tempfile.gettempdir(), "downloaded_videos")
    os.makedirs(downloads_dir, exist_ok=True)

    filename = _sanitize(custom_filename or video_id)
    output_path = os.path.join(downloads_dir, f"{filename}.mp4")

    if os.path.exists(output_path):
        print(f"[download] Cached: {output_path}")
        return output_path

    if _PROXY_URL:
        _download_via_proxy(url, output_path)
    else:
        _download_via_ytdlp(url, output_path)

    return output_path


# --- Strategy 1: Download Proxy (production) ---

def _download_via_proxy(url: str, output_path: str) -> None:
    """Call the home download proxy to fetch the video."""
    endpoint = f"{_PROXY_URL}/download"
    headers = {"Content-Type": "application/json"}
    if _PROXY_KEY:
        headers["Authorization"] = f"Bearer {_PROXY_KEY}"

    print(f"[proxy] Requesting download from proxy: {url}")

    resp = requests.post(
        endpoint,
        json={"url": url},
        headers=headers,
        stream=True,
        timeout=_PROXY_TIMEOUT,
    )

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Download proxy error ({resp.status_code}): {detail}")

    # Stream response body to disk
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    size = os.path.getsize(output_path)
    if size < 100_000:
        os.remove(output_path)
        raise RuntimeError(f"Proxy returned a file too small ({size} bytes)")

    print(f"[proxy] Downloaded {size / 1024 / 1024:.1f} MB → {output_path}")


# --- Strategy 2: yt-dlp direct (local dev) ---

def _download_via_ytdlp(url: str, output_path: str) -> None:
    """Download directly with yt-dlp (works from residential IPs)."""
    print(f"[yt-dlp] Downloading: {url}")

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(output_path):
        raise RuntimeError("yt-dlp finished but no file was created")

    print(f"[yt-dlp] Downloaded → {output_path}")


# --- Helpers ---

def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        # /embed/ID format
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0]

    if host in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("/")[0].split("?")[0]

    return None


def _sanitize(name: str) -> str:
    """Remove unsafe characters from a filename."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "-", "_")).strip() or "video"
