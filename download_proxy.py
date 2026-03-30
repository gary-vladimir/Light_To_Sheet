"""
Light to Sheet — YouTube Download Proxy

A tiny server that runs on your Mac (residential IP) and downloads
YouTube videos on behalf of the Cloud Run app.  Exposed to the
internet via Cloudflare Tunnel (free).

Usage:
    PROXY_API_KEY=your-secret python download_proxy.py

See DOWNLOAD_PROXY_SETUP.md for full setup instructions.
"""

from __future__ import annotations

import glob
import hmac
import os
import shutil
import tempfile
import time

import yt_dlp
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

API_KEY = os.environ.get("PROXY_API_KEY", "")

# --- Piano-content filter ---

_PIANO_KEYWORDS = [
    # Core — "piano" alone matches: piano cover, piano tutorial, piano solo,
    # grand piano, digital piano, piano lesson, etc.
    "piano",
    # "pianist" does NOT contain "piano" as a substring
    "pianist",
    # Unique terms that don't contain "piano"
    "synthesia",
    "sheet music",
    "keyboard cover",
    "keyboard tutorial",
    # Well-known piano YouTube channels
    "rousseau", "kassia", "animenz", "marioverehrer",
    "pianella", "patrik pietschmann", "sheet music boss",
    "fonzi m", "thepianoguys",
]


class _MetadataError(Exception):
    """Failed to extract video metadata (network, age-gate, etc.)."""
    pass


def _check_piano_video(url: str) -> None:
    """Check video metadata to determine if it's piano-related.

    Raises:
        _MetadataError: If metadata extraction fails (yt-dlp/network error).
        ValueError: If the video is not piano-related.
    """
    try:
        info = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}).extract_info(
            url, download=False,
        )
    except Exception as e:
        raise _MetadataError(f"Could not fetch video metadata: {e}") from e

    searchable = " ".join([
        info.get("title", ""),
        info.get("description", ""),
        " ".join(info.get("tags") or []),
        " ".join(info.get("categories") or []),
        info.get("channel", ""),
        info.get("uploader", ""),
    ]).lower()

    if not any(kw in searchable for kw in _PIANO_KEYWORDS):
        raise ValueError("Video does not appear to be piano-related")


def _check_auth():
    """Verify the Bearer token matches our API key (constant-time)."""
    if not API_KEY:
        return  # No key configured — allow all (local dev only)
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, API_KEY):
        return jsonify({"error": "Unauthorized"}), 401


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/download", methods=["POST"])
def download():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing 'url' field"}), 400

    try:
        _check_piano_video(url)
    except _MetadataError as e:
        print(f"[proxy] Metadata extraction failed: {e}")
        return jsonify({"error": f"Could not check video metadata: {e}"}), 502
    except ValueError:
        print(f"[proxy] Rejected (not piano-related): {url}")
        return jsonify({"error": "Video does not appear to be piano-related"}), 403

    # Download to a temp file
    tmp_dir = tempfile.mkdtemp(prefix="lts_proxy_")
    output_path = os.path.join(tmp_dir, "video.mp4")

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        print(f"[proxy] Downloading: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_path):
            return jsonify({"error": "Download produced no file"}), 500

        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[proxy] Done: {size_mb:.1f} MB")

        # Stream the file back, then clean up
        return send_file(
            output_path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name="video.mp4",
        )
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[proxy] Failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.after_request
def _cleanup(response):
    """Clean up old temp directories from previous requests.

    The current request's temp dir may still be streaming, so we only
    delete directories older than 5 minutes.
    """
    cutoff = time.time() - 300  # 5 minutes ago
    for tmp_dir in glob.glob(os.path.join(tempfile.gettempdir(), "lts_proxy_*")):
        try:
            if os.path.getmtime(tmp_dir) < cutoff:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except OSError:
            pass
    return response


if __name__ == "__main__":
    import sys

    port = int(os.environ.get("PROXY_PORT", 8787))
    print(f"[proxy] Starting download proxy on port {port}")
    if not API_KEY:
        print("[proxy] ERROR: PROXY_API_KEY is required. Set it as an environment variable.")
        sys.exit(1)
    print(f"[proxy] API key is set (length={len(API_KEY)})")

    # Use Gunicorn in production, fall back to Flask dev server if unavailable
    try:
        from gunicorn.app.base import BaseApplication

        class _StandaloneApp(BaseApplication):
            def __init__(self, flask_app, options):
                self.flask_app = flask_app
                self.options = options
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.flask_app

        _StandaloneApp(app, {
            "bind": f"0.0.0.0:{port}",
            "workers": 2,
            "timeout": 900,  # 15 min — long downloads
        }).run()
    except ImportError:
        print("[proxy] WARNING: gunicorn not installed, using Flask dev server")
        app.run(host="0.0.0.0", port=port, debug=False)
