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
from .frame_analyzer import analyze_frame_brightness
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

    print(f"Video preprocessed: {frame_count} frames at {fps:.0f}fps ({width}x{height})")
    return output_path


def process_video(
    video_path: str,
    output_file: str = "output.txt",
    save_previews: bool = True,
) -> None:
    """Process video frames and extract brightness data.

    Reads the video frame-by-frame, detects which piano keys are pressed
    via brightness analysis, and writes the results to multiple output files.
    Processing runs at real-time speed (1/FPS delay per frame) so the
    standardized frame rate maps directly to note durations.

    Args:
        video_path: Path to preprocessed video file.
        output_file: Path for raw output file.
        save_previews: Whether to save annotated preview frames.
    """
    print("Processing video frames...")

    preview_dir: str | None = None
    if save_previews:
        preview_dir = "preview_frames"
        os.makedirs(preview_dir, exist_ok=True)
        print(f"Saving preview frames to: {preview_dir}/")
        print(f"Preview frames saved every {PREVIEW_SAVE_INTERVAL} frames "
              f"({VIDEO_FPS // PREVIEW_SAVE_INTERVAL} previews per second)")

    cap = cv2.VideoCapture(video_path)
    cv2.setLogLevel(0)  # Suppress OpenCV warnings

    frame_duration = 1.0 / VIDEO_FPS
    frame_number = 0
    failed_frames = 0

    with OutputWriter(output_file) as writer:
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
                brightness_values, vis_frame = analyze_frame_brightness(frame, visualize=True)
                _save_preview(vis_frame, preview_dir, frame_number, timestamp_str, brightness_values)
            else:
                brightness_values = analyze_frame_brightness(frame)

            # Console progress (once per second)
            if frame_number % VIDEO_FPS == 0:
                output_line = f"{brightness_values} {timestamp_str}"
                print(f"Frame {frame_number}: {output_line[:50]}... {timestamp_str}")

            writer.write_frame(brightness_values, timestamp_str)

            # Real-time pacing — ensures 24 frames = 1 second of music
            time.sleep(frame_duration)
            frame_number += 1

    cap.release()

    # Summary
    print(f"\nProcessing complete. Total frames: {frame_number}")
    if failed_frames > 0:
        print(f"Warning: {failed_frames} corrupted frame(s) were skipped")
    print(f"Results saved to: {output_file}")
    print(f"Piano CSV saved to: piano.csv")
    if preview_dir is not None:
        print(f"Preview frames saved to: {preview_dir}/")
        print(f"Total preview frames: {frame_number // PREVIEW_SAVE_INTERVAL}")


def _save_preview(
    vis_frame,
    preview_dir: str,
    frame_number: int,
    timestamp_str: str,
    brightness_values: list[int],
) -> None:
    """Add text overlays to a visualization frame and save it (every N frames).

    Args:
        vis_frame: Annotated visualization frame from the analyzer.
        preview_dir: Directory to save preview images.
        frame_number: Current frame index.
        timestamp_str: Formatted timestamp for the frame.
        brightness_values: Binary key states (used for active-key count).
    """
    # Frame info overlay
    info_text = f"Frame: {frame_number} | Time: {timestamp_str}"
    cv2.putText(vis_frame, info_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Active key count overlay (not misleading "brightness %" from binary values)
    active_count = sum(brightness_values)
    total_keys = len(brightness_values)
    stats_text = f"Active keys: {active_count} / {total_keys}"
    cv2.putText(vis_frame, stats_text, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Save every Nth frame
    if frame_number % PREVIEW_SAVE_INTERVAL == 0:
        preview_path = os.path.join(preview_dir, f"frame_{frame_number:06d}.jpg")
        cv2.imwrite(preview_path, vis_frame)
        # Log once per second to reduce console noise
        if frame_number % VIDEO_FPS == 0:
            print(f"Saved preview: {preview_path}")
