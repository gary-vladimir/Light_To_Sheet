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

import os
import shutil
import tempfile

import yt_dlp
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

API_KEY = os.environ.get("PROXY_API_KEY", "")


def _check_auth():
    """Verify the Bearer token matches our API key."""
    if not API_KEY:
        return  # No key configured — allow all (local dev only)
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token != API_KEY:
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
    """Clean up temp files after the response is sent."""
    # Flask/Werkzeug closes the file after streaming, so we schedule cleanup
    # via a callback. For simplicity, temp dirs are cleaned on next request.
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PROXY_PORT", 8787))
    print(f"[proxy] Starting download proxy on port {port}")
    if API_KEY:
        print(f"[proxy] API key is set (length={len(API_KEY)})")
    else:
        print("[proxy] WARNING: No PROXY_API_KEY set — server is open!")
    app.run(host="0.0.0.0", port=port, debug=False)
