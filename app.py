"""
Light to Sheet — Web Application

A minimal Flask app that wraps the piano note detection algorithm,
letting users paste a YouTube URL or upload a video file and receive
sheet music output without needing a terminal.

Run as: python app.py
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid

from flask import Flask, jsonify, render_template, request, send_file

from src.video_downloader import download_youtube_video
from src.video_processor import preprocess_video, process_video

app = Flask(__name__)

# Max upload size: 500 MB
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

JOBS_DIR = os.path.join(tempfile.gettempdir(), "light_to_sheet_jobs")
ALLOWED_OUTPUT_FILES = {"output.txt", "piano.csv", "sheet_music.txt"}


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def api_process():
    """Accept a YouTube URL or uploaded video, process it, return results."""
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    try:
        video_path = _get_input_video(request, job_dir)
    except ValueError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400

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
        return jsonify({"error": f"Processing failed: {e}"}), 500
    finally:
        # Clean up the large preprocessed file (keep output files)
        if os.path.exists(processed_path):
            os.remove(processed_path)
        # Clean up uploaded input file
        input_file = os.path.join(job_dir, "input.mp4")
        if os.path.exists(input_file):
            os.remove(input_file)

    # Read sheet music for inline display
    sheet_music_path = os.path.join(job_dir, "sheet_music.txt")
    sheet_music = ""
    if os.path.exists(sheet_music_path):
        with open(sheet_music_path) as f:
            sheet_music = f.read()

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
        "files": list(ALLOWED_OUTPUT_FILES),
        "preview_frames": preview_frames,
    })


@app.route("/api/download/<job_id>/<filename>")
def api_download(job_id: str, filename: str):
    """Serve an output file for download."""
    # Validate to prevent path traversal
    if filename not in ALLOWED_OUTPUT_FILES:
        return jsonify({"error": "Invalid filename"}), 400

    # Validate job_id is a UUID (no slashes or dots)
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job ID"}), 400

    file_path = os.path.join(JOBS_DIR, job_id, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, as_attachment=True, download_name=filename)


@app.route("/api/preview/<job_id>/<filename>")
def api_preview(job_id: str, filename: str):
    """Serve a preview frame image."""
    # Validate job_id is a UUID
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job ID"}), 400

    # Validate filename matches expected pattern (prevent path traversal)
    if not re.fullmatch(r"frame_\d{6}\.jpg", filename):
        return jsonify({"error": "Invalid filename"}), 400

    file_path = os.path.join(JOBS_DIR, job_id, "preview_frames", filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_file(file_path, mimetype="image/jpeg")


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
        try:
            return download_youtube_video(youtube_url)
        except Exception as e:
            raise ValueError(f"Failed to download video: {e}") from e

    if video_file and video_file.filename:
        input_path = os.path.join(job_dir, "input.mp4")
        video_file.save(input_path)
        return input_path

    raise ValueError("Please provide a YouTube URL or upload a video file.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
