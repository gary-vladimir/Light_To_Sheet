"""
Frame analysis functionality for Light to Sheet.

This module detects piano key presses by measuring **color distance from a
calibrated background** across narrow sampling strips for each of the 88
piano keys.  White and black keys are handled separately to avoid spillover
false positives caused by overlapping light bars in Synthesia-style videos.

Detection pipeline:
  0. calibrate_background() — estimate per-key background BGR from first N frames
  1. Per-frame: compute Euclidean BGR distance from background for each key
  2. Spillover correction on black keys (same ratio logic, using distances)
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from .config import (
    CALIBRATION_FRAMES,
    COLOR_DISTANCE_THRESHOLD,
    KEY_GEOMETRY,
    NUM_WHITE_KEYS,
    PIANO_NOTES,
    SPILLOVER_RATIO,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    WHITE_KEY_WIDTH,
)


# Maximum possible Euclidean distance in BGR space (black ↔ white).
_MAX_COLOR_DISTANCE: float = float(np.linalg.norm([255, 255, 255]))  # ~441.67


def calibrate_background(video_path: str) -> NDArray[np.float32]:
    """Estimate per-key background colors from the first N frames.

    Opens the video, reads up to ``CALIBRATION_FRAMES`` frames, and computes
    the **median** BGR color of each key's sampling region across those frames.
    The median is robust to outliers (keys that happen to be pressed during the
    calibration window).

    Args:
        video_path: Path to the preprocessed video file.

    Returns:
        Array of shape ``(88, 3)`` — one BGR triplet per key.

    Raises:
        RuntimeError: If the video cannot be opened or has no readable frames.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video for calibration: {video_path}")

    # Collect per-key BGR samples: list of (88, 3) arrays, one per frame.
    frame_samples: list[NDArray[np.float32]] = []

    for _ in range(CALIBRATION_FRAMES):
        ret, frame = cap.read()
        if not ret:
            break

        key_colors = np.empty((len(KEY_GEOMETRY), 3), dtype=np.float32)
        for idx, geo in enumerate(KEY_GEOMETRY):
            region = frame[0:1, geo["x_start"]:geo["x_end"]]  # (1, W, 3) BGR
            key_colors[idx] = np.mean(region.reshape(-1, 3), axis=0)

        frame_samples.append(key_colors)

    cap.release()

    if not frame_samples:
        raise RuntimeError("No frames could be read during calibration")

    # Stack into (N, 88, 3) and take per-key median across frames.
    stacked = np.stack(frame_samples, axis=0)  # (N, 88, 3)
    background = np.median(stacked, axis=0).astype(np.float32)  # (88, 3)

    print(f"Background calibrated from {len(frame_samples)} frames "
          f"(mean bg color: BGR {background.mean(axis=0).astype(int)})")

    return background


def analyze_frame_brightness(
    frame: NDArray[np.uint8],
    background: NDArray[np.float32],
    visualize: bool = False,
) -> list[int] | tuple[list[int], NDArray[np.uint8]]:
    """Detect which piano keys are pressed by color distance from background.

    Phase 1 — Sample all 88 keys at their narrow center strips in BGR.
              Compute Euclidean distance from the calibrated background.
    Phase 2 — Spillover correction: for each detected black key, check if
              its distance is significantly lower than a pressed white
              neighbor.  If so, the detection is spillover — remove it.

    Args:
        frame: BGR video frame (numpy array).
        background: Per-key background colors, shape (88, 3), from
            :func:`calibrate_background`.
        visualize: If True, also returns an annotated visualization frame.

    Returns:
        If visualize is False: list of 88 binary values (0 or 1).
        If visualize is True: tuple of (binary values, annotated frame).
    """
    # ------------------------------------------------------------------
    # Phase 1: color-distance sampling (all 88 keys)
    # ------------------------------------------------------------------
    raw_distances: list[float] = []
    brightness_values: list[int] = []

    for idx, geo in enumerate(KEY_GEOMETRY):
        region = frame[0:1, geo["x_start"]:geo["x_end"]]  # (1, W, 3) BGR
        avg_bgr = np.mean(region.reshape(-1, 3), axis=0)  # (3,)

        distance = float(np.linalg.norm(avg_bgr - background[idx]))
        raw_distances.append(distance)
        brightness_values.append(1 if distance > COLOR_DISTANCE_THRESHOLD else 0)

    # ------------------------------------------------------------------
    # Phase 2: spillover correction (black keys only)
    # ------------------------------------------------------------------
    removed_by_spillover: list[bool] = [False] * 88

    for i, geo in enumerate(KEY_GEOMETRY):
        if not geo["is_black"]:
            continue
        if brightness_values[i] == 0:
            continue

        # Find the largest distance among pressed white neighbors
        max_white_dist = 0.0
        for neighbor_idx in (geo["left_white_idx"], geo["right_white_idx"]):
            if neighbor_idx is not None and brightness_values[neighbor_idx] == 1:
                if raw_distances[neighbor_idx] > max_white_dist:
                    max_white_dist = raw_distances[neighbor_idx]

        # If no white neighbor is pressed, this black key is genuine — skip
        if max_white_dist == 0.0:
            continue

        # If the black key's distance is much lower than the neighbor, spillover
        if raw_distances[i] < max_white_dist * SPILLOVER_RATIO:
            brightness_values[i] = 0
            removed_by_spillover[i] = True

    # ------------------------------------------------------------------
    # Phase 3: visualization (optional)
    # ------------------------------------------------------------------
    if visualize:
        vis_frame = frame.copy()
        # Yellow line highlighting the 1px analysis zone
        cv2.rectangle(vis_frame, (0, 0), (VIDEO_WIDTH, 1), (0, 255, 255), 2)

        # White-zone dividers (thin gray lines every ~35.5px)
        for w in range(1, NUM_WHITE_KEYS):
            x = int(round(w * WHITE_KEY_WIDTH))
            cv2.line(vis_frame, (x, 0), (x, 50), (100, 100, 100), 1)

        for i, geo in enumerate(KEY_GEOMETRY):
            _draw_key_visualization(
                vis_frame, i,
                geo["x_start"], geo["x_end"],
                raw_distances[i],
                geo["is_black"],
                removed_by_spillover[i],
            )

        return brightness_values, vis_frame

    return brightness_values


def _draw_key_visualization(
    vis_frame: NDArray[np.uint8],
    key_index: int,
    x_start: int,
    x_end: int,
    color_distance: float,
    is_black: bool,
    was_removed: bool,
) -> None:
    """Draw visualization overlay for a single key onto the frame.

    Args:
        vis_frame: Frame to draw on (modified in place).
        key_index: Index of the current key (0-87).
        x_start: Left pixel boundary of the sampling strip.
        x_end: Right pixel boundary of the sampling strip.
        color_distance: Euclidean BGR distance from background (0–~441).
        is_black: Whether this is a black key.
        was_removed: Whether this key was removed by spillover correction.
    """
    # Sampling-strip indicator (drawn just below the yellow analysis zone)
    if is_black:
        strip_color = (200, 0, 200)  # magenta for black keys
    else:
        strip_color = (200, 200, 0)  # cyan for white keys
    cv2.rectangle(vis_frame, (x_start, 3), (x_end - 1, 8), strip_color, -1)

    # Color-distance bar at the bottom of the frame
    # Normalize distance to 0–255 for color intensity and 0–150 for bar height
    norm = min(color_distance / _MAX_COLOR_DISTANCE, 1.0)
    intensity = int(norm * 255)

    if is_black:
        color = (intensity, 0, 255 - intensity)       # blue gradient for black keys
    else:
        color = (0, intensity, 255 - intensity)        # green gradient for white keys

    bar_height = int(norm * 150)
    cv2.rectangle(
        vis_frame,
        (x_start, VIDEO_HEIGHT - bar_height),
        (x_end - 1, VIDEO_HEIGHT),
        color,
        -1,
    )

    # Mark spillover-removed keys with a red X
    if was_removed:
        bar_top = VIDEO_HEIGHT - bar_height
        bar_bottom = VIDEO_HEIGHT
        cv2.line(vis_frame, (x_start, bar_top), (x_end - 1, bar_bottom), (0, 0, 255), 2)
        cv2.line(vis_frame, (x_start, bar_bottom), (x_end - 1, bar_top), (0, 0, 255), 2)

    # Label every 11th key to avoid clutter
    if key_index % 11 == 0:
        label = PIANO_NOTES[key_index]
        cv2.putText(
            vis_frame,
            label,
            (x_start + 2, VIDEO_HEIGHT - bar_height - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            (255, 255, 255),
            1,
        )
