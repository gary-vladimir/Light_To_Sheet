"""
Light to Sheet — Web Application

A Flask app that wraps the piano note detection algorithm,
letting users paste a YouTube URL or upload a video file and receive
sheet music output without needing a terminal. Protected by Firebase Authentication.

Run locally:  DEBUG=1 python app.py
Production:   gunicorn app:app
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import time
import uuid

import firebase_admin
from firebase_admin import auth as firebase_auth
from flask import Flask, jsonify, render_template, request, send_file

from src.video_downloader import download_youtube_video, NotPianoError, DownloadFailedError
from src.video_processor import preprocess_video, process_video

app = Flask(__name__)

# Max upload size: 500 MB
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

# Initialize Firebase Admin SDK.
# On Cloud Run: uses Application Default Credentials automatically.
# Locally: set GOOGLE_APPLICATION_CREDENTIALS env var to a service account JSON.
# If no credentials are available (local dev), auth is disabled with a warning.
_firebase_initialized = False
try:
    firebase_admin.initialize_app()
    _firebase_initialized = True
except Exception:
    logging.warning(
        "Firebase credentials not found — auth is DISABLED. "
        "Set GOOGLE_APPLICATION_CREDENTIALS for local Firebase auth testing."
    )

JOBS_DIR = os.path.join(tempfile.gettempdir(), "light_to_sheet_jobs")
ALLOWED_OUTPUT_FILES = {"output.txt", "piano.csv", "sheet_music.txt"}
_RATE_LIMIT_SECONDS = 60
_user_last_request: dict[str, float] = {}

log = logging.getLogger(__name__)


def verify_firebase_token(req) -> dict:
    """Extract and verify the Firebase ID token from the Authorization header.

    Returns the decoded token claims (contains 'uid', 'email', 'name', etc.).
    Raises ValueError if missing or invalid.

    When Firebase is not initialized (local dev without credentials),
    auth is bypassed and a placeholder user dict is returned.
    """
    if not _firebase_initialized:
        return {"uid": "local-dev", "email": "dev@localhost"}

    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Authentication required")

    id_token = auth_header.split("Bearer ", 1)[1]
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as e:
        raise ValueError(f"Invalid authentication token: {e}") from e


@app.after_request
def _set_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/")
def index() -> str:
    return render_template("index.html")


_JOB_MAX_AGE_SECONDS = 3600  # 1 hour


def _cleanup_old_jobs() -> None:
    """Delete job directories older than 1 hour. Best-effort, never raises."""
    if not os.path.isdir(JOBS_DIR):
        return
    cutoff = time.time() - _JOB_MAX_AGE_SECONDS
    try:
        for name in os.listdir(JOBS_DIR):
            job_path = os.path.join(JOBS_DIR, name)
            if os.path.isdir(job_path) and os.path.getmtime(job_path) < cutoff:
                shutil.rmtree(job_path, ignore_errors=True)
    except OSError:
        pass


@app.route("/api/process", methods=["POST"])
def api_process():
    """Accept a YouTube URL or uploaded video, process it, return results. Requires authentication."""
    # Verify Firebase auth token
    try:
        user = verify_firebase_token(request)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    uid = user["uid"]
    now = time.time()
    last = _user_last_request.get(uid, 0)
    if now - last < _RATE_LIMIT_SECONDS:
        wait = int(_RATE_LIMIT_SECONDS - (now - last)) + 1
        return jsonify({
            "error_type": "rate_limited",
            "error": f"Please wait {wait} seconds before submitting another video.",
        }), 429
    _user_last_request[uid] = now

    _cleanup_old_jobs()

    log.info("Processing request from user %s", user.get("email", uid))

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # Store owner for access control on download/preview endpoints
    with open(os.path.join(job_dir, ".owner"), "w") as f:
        f.write(user["uid"])

    try:
        video_path = _get_input_video(request, job_dir)
    except NotPianoError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({
            "error_type": "not_piano",
            "error": "This video doesn't appear to be piano-related",
            "detail": "We check the video's title, description, tags, and channel for piano-related content.",
        }), 400
    except DownloadFailedError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        log.warning("Download failed: %s", e)
        return jsonify({
            "error_type": "download_failed",
            "error": "Couldn't download this video",
            "detail": "YouTube may block server-side downloads. Try the Upload Video tab instead.",
        }), 400
    except ValueError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error_type": "validation", "error": str(e)}), 400

    # Preprocess and process
    processed_path = os.path.join(job_dir, "processed.mp4")
    try:
        preprocess_video(video_path, processed_path)
        process_video(
            processed_path,
            output_dir=job_dir,
            save_previews=True,
            realtime=False,
        )
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        log.exception("Processing failed for job %s", job_id)
        return jsonify({
            "error_type": "processing_failed",
            "error": "Something went wrong while processing the video",
            "detail": "Try a different video or a shorter clip. If this keeps happening, the video format may not be supported.",
        }), 500
    finally:
        # Clean up large video files (keep output files)
        for vid_name in ("processed.mp4", "input.mp4", "downloaded.mp4"):
            vid_path = os.path.join(job_dir, vid_name)
            if os.path.exists(vid_path):
                os.remove(vid_path)

    # Read sheet music for inline display (truncate if huge to avoid crashing browser)
    _SHEET_MUSIC_MAX_DISPLAY = 500_000  # ~500 KB
    sheet_music_path = os.path.join(job_dir, "sheet_music.txt")
    sheet_music = ""
    sheet_music_truncated = False
    if os.path.exists(sheet_music_path):
        with open(sheet_music_path) as f:
            sheet_music = f.read(_SHEET_MUSIC_MAX_DISPLAY + 1)
        if len(sheet_music) > _SHEET_MUSIC_MAX_DISPLAY:
            sheet_music = sheet_music[:_SHEET_MUSIC_MAX_DISPLAY]
            sheet_music_truncated = True

    # List saved preview frames (sorted by filename → chronological order)
    preview_frames: list[str] = []
    preview_dir = os.path.join(job_dir, "preview_frames")
    if os.path.isdir(preview_dir):
        preview_frames = sorted(
            f for f in os.listdir(preview_dir) if f.endswith(".jpg")
        )

    return jsonify({
        "job_id": job_id,
        "sheet_music": sheet_music,
        "sheet_music_truncated": sheet_music_truncated,
        "files": [f for f in ALLOWED_OUTPUT_FILES if os.path.exists(os.path.join(job_dir, f))],
        "preview_frames": preview_frames,
    })


def _verify_job_owner(job_id: str, req) -> str | tuple:
    """Validate job_id and check ownership. Returns job_dir or an error response."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job ID"}), 400

    job_dir = os.path.join(JOBS_DIR, job_id)
    owner_file = os.path.join(job_dir, ".owner")
    if not os.path.isdir(job_dir):
        return jsonify({"error": "File not found"}), 404

    # Check ownership (skip if no .owner file — legacy jobs)
    if os.path.exists(owner_file):
        try:
            user = verify_firebase_token(req)
        except ValueError:
            return jsonify({"error": "Authentication required"}), 401
        with open(owner_file) as f:
            if f.read().strip() != user["uid"]:
                return jsonify({"error": "File not found"}), 404

    return job_dir


@app.route("/api/download/<job_id>/<filename>")
def api_download(job_id: str, filename: str):
    """Serve an output file for download."""
    if filename not in ALLOWED_OUTPUT_FILES:
        return jsonify({"error": "Invalid filename"}), 400

    result = _verify_job_owner(job_id, request)
    if isinstance(result, tuple):
        return result
    job_dir = result

    file_path = os.path.join(job_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, as_attachment=True, download_name=filename)


@app.route("/api/preview/<job_id>/<filename>")
def api_preview(job_id: str, filename: str):
    """Serve a preview frame image."""
    if not re.fullmatch(r"frame_\d{6}\.jpg", filename):
        return jsonify({"error": "Invalid filename"}), 400

    result = _verify_job_owner(job_id, request)
    if isinstance(result, tuple):
        return result
    job_dir = result

    file_path = os.path.join(job_dir, "preview_frames", filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, mimetype="image/jpeg")


# Magic bytes for common video formats
_VIDEO_SIGNATURES = [
    (4, b"ftyp"),       # MP4 / M4V / MOV (offset 4)
    (0, b"\x1a\x45\xdf\xa3"),  # WebM / MKV (EBML header)
    (0, b"RIFF"),       # AVI
    (0, b"\x00\x00\x01\xba"),  # MPEG-PS
    (0, b"\x00\x00\x01\xb3"),  # MPEG-1/2
    (0, b"\x46\x4c\x56"),      # FLV
]


def _validate_video_file(path: str) -> None:
    """Check that an uploaded file looks like a video (magic byte check).

    Raises ValueError if the file doesn't match any known video signature.
    """
    with open(path, "rb") as f:
        header = f.read(12)
    if len(header) < 8:
        raise ValueError("Uploaded file is too small to be a video.")
    for offset, signature in _VIDEO_SIGNATURES:
        if header[offset:offset + len(signature)] == signature:
            return
    raise ValueError(
        "Uploaded file doesn't appear to be a video. "
        "Supported formats: MP4, WebM, MKV, AVI, MOV."
    )


def _get_input_video(req, job_dir: str) -> str:
    """Extract the video path from the request (YouTube URL or file upload).

    Args:
        req: Flask request object.
        job_dir: Directory to save uploaded files.

    Returns:
        Path to the video file.

    Raises:
        ValueError: If no valid input is provided.
    """
    youtube_url = req.form.get("youtube_url", "").strip()
    video_file = req.files.get("video_file")

    if youtube_url:
        return download_youtube_video(youtube_url, job_dir)

    if video_file and video_file.filename:
        input_path = os.path.join(job_dir, "input.mp4")
        video_file.save(input_path)
        _validate_video_file(input_path)
        return input_path

    raise ValueError("Please provide a YouTube URL or upload a video file.")


if __name__ == "__main__":
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, host="0.0.0.0", port=port)
