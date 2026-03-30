"""
Video processing functionality for Light to Sheet.

This module handles:
- Video preprocessing (resizing, FPS conversion) using FFmpeg
- Frame-by-frame video processing
- Integration of frame analysis and output writing
"""

from __future__ import annotations

import os
import subprocess
import time

import cv2

from .config import (
    PREVIEW_SAVE_INTERVAL,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from .frame_analyzer import analyze_frame_brightness, calibrate_background
from .output_writer import OutputWriter
from .utils import format_timestamp


def preprocess_video(input_path: str, output_path: str) -> str:
    """Resize video to target dimensions and convert to target FPS using FFmpeg.

    Uses FFmpeg directly (rather than OpenCV) to avoid frame-seeking issues
    that cause H.264 decoding errors.

    Args:
        input_path: Path to input video file.
        output_path: Path to save preprocessed video.

    Returns:
        Path to preprocessed video.

    Raises:
        RuntimeError: If FFmpeg fails or the output cannot be opened.
    """
    print("Preprocessing video...")

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=disable,fps={VIDEO_FPS}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",
        "-loglevel", "error",
        output_path,
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg preprocessing failed: {e.stderr}") from e

    # Verify the output is readable
    cap = cv2.VideoCapture(output_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open preprocessed video: {output_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    # Reject videos longer than 30 minutes to prevent memory/timeout issues
    if fps > 0 and frame_count > 0:
        duration_minutes = frame_count / fps / 60
        if duration_minutes > 30:
            raise RuntimeError(
                f"Video is too long ({duration_minutes:.0f} minutes). "
                f"Maximum supported duration is 30 minutes."
            )

    print(f"Video preprocessed: {frame_count} frames at {fps:.0f}fps ({width}x{height})")
    return output_path


def process_video(
    video_path: str,
    output_dir: str = ".",
    save_previews: bool = True,
    realtime: bool = True,
) -> None:
    """Process video frames and extract brightness data.

    Reads the video frame-by-frame, detects which piano keys are pressed
    via brightness analysis, and writes the results to multiple output files.

    Args:
        video_path: Path to preprocessed video file.
        output_dir: Directory where output files are written.
        save_previews: Whether to save annotated preview frames.
        realtime: If True, sleep 1/FPS per frame (real-time pacing for CLI).
                  If False, process as fast as possible (web mode).
    """
    print("Processing video frames...")

    # Phase 0: calibrate per-key background colors from first N frames
    background = calibrate_background(video_path)

    output_file = os.path.join(output_dir, "output.txt")
    piano_csv = os.path.join(output_dir, "piano.csv")
    sheet_music_file = os.path.join(output_dir, "sheet_music.txt")

    preview_dir: str | None = None
    if save_previews:
        preview_dir = os.path.join(output_dir, "preview_frames")
        os.makedirs(preview_dir, exist_ok=True)
        print(f"Saving preview frames to: {preview_dir}/")
        print(f"Preview frames saved every {PREVIEW_SAVE_INTERVAL} frames "
              f"({VIDEO_FPS // PREVIEW_SAVE_INTERVAL} previews per second)")

    cap = cv2.VideoCapture(video_path)

    # Suppress OpenCV warnings (not available in all builds)
    if hasattr(cv2, "setLogLevel"):
        cv2.setLogLevel(0)

    frame_duration = 1.0 / VIDEO_FPS
    frame_number = 0
    failed_frames = 0

    with OutputWriter(output_file, piano_csv, sheet_music_file) as writer:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame is None or frame.size == 0:
                print(f"Warning: Skipping corrupted frame {frame_number}")
                failed_frames += 1
                frame_number += 1
                continue

            timestamp = frame_number * frame_duration
            timestamp_str = format_timestamp(timestamp)

            # Analyze frame (with or without visualization)
            if preview_dir is not None:
                brightness_values, vis_frame, frame_meta = analyze_frame_brightness(frame, background, visualize=True)
                _save_preview(vis_frame, preview_dir, frame_number, timestamp_str,
                              brightness_values, frame_meta)
            else:
                brightness_values = analyze_frame_brightness(frame, background)

            # Console progress (once per second)
            if frame_number % VIDEO_FPS == 0:
                output_line = f"{brightness_values} {timestamp_str}"
                print(f"Frame {frame_number}: {output_line[:50]}... {timestamp_str}")

            writer.write_frame(brightness_values, timestamp_str)

            if realtime:
                time.sleep(frame_duration)

            frame_number += 1

    cap.release()

    # Summary
    print(f"\nProcessing complete. Total frames: {frame_number}")
    if failed_frames > 0:
        print(f"Warning: {failed_frames} corrupted frame(s) were skipped")
    print(f"Results saved to: {output_file}")
    print(f"Piano CSV saved to: {piano_csv}")
    if preview_dir is not None:
        print(f"Preview frames saved to: {preview_dir}/")
        print(f"Total preview frames: {frame_number // PREVIEW_SAVE_INTERVAL}")


def _save_preview(
    vis_frame,
    preview_dir: str,
    frame_number: int,
    timestamp_str: str,
    brightness_values: list[int],
    frame_meta: dict,
) -> None:
    """Add text overlays to a visualization frame and save it (every N frames).

    Args:
        vis_frame: Annotated visualization frame from the analyzer.
        preview_dir: Directory to save preview images.
        frame_number: Current frame index.
        timestamp_str: Formatted timestamp for the frame.
        brightness_values: Binary key states (used for active-key count).
        frame_meta: Detection metadata (threshold, median, active notes, etc.).
    """
    active_count = sum(brightness_values)
    threshold = frame_meta["adaptive_threshold"]
    median = frame_meta["median_distance"]
    active_notes = frame_meta["active_notes"]
    spillover_count = sum(frame_meta["removed_by_spillover"])

    # Dark background for text readability
    panel_height = 100 if spillover_count == 0 else 118
    cv2.rectangle(vis_frame, (0, 0), (520, panel_height), (0, 0, 0), -1)

    # Line 1: frame info
    cv2.putText(vis_frame, f"Frame: {frame_number} | Time: {timestamp_str}",
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Line 2: detection stats
    cv2.putText(vis_frame,
                f"Active: {active_count}/88 | Threshold: {threshold:.0f} | Median: {median:.0f}",
                (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    # Line 3: active note names
    notes_str = " ".join(active_notes[:12])
    if len(active_notes) > 12:
        notes_str += " ..."
    cv2.putText(vis_frame, f"Notes: {notes_str}",
                (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 50), 1)

    # Line 4: spillover count (only if > 0)
    if spillover_count > 0:
        cv2.putText(vis_frame, f"Spillover removed: {spillover_count}",
                    (10, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 140, 255), 1)

    # Save every Nth frame
    if frame_number % PREVIEW_SAVE_INTERVAL == 0:
        preview_path = os.path.join(preview_dir, f"frame_{frame_number:06d}.jpg")
        cv2.imwrite(preview_path, vis_frame)
        # Log once per second to reduce console noise
        if frame_number % VIDEO_FPS == 0:
            print(f"Saved preview: {preview_path}")
