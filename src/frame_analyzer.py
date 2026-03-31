"""
Frame analysis functionality for Light to Sheet.

This module detects piano key presses by measuring **color distance from a
calibrated background** across narrow sampling strips for each of the 88
piano keys.  White and black keys are handled separately to avoid spillover
false positives caused by overlapping light bars in Synthesia-style videos.

Detection pipeline:
  0. calibrate_background() — estimate per-key background BGR from first N frames
  1. Per-frame: compute Euclidean BGR distance from background for each key
  2. Spillover correction on all keys (ratio-based neighbor comparison)
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
    try:
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
    finally:
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
    Phase 2 — Spillover correction: for each detected key, check if its
              distance is significantly lower than a nearby pressed
              neighbor (±2 positions).  If so, the detection is light
              spillover from the brighter neighbor — remove it.

    Args:
        frame: BGR video frame (numpy array).
        background: Per-key background colors, shape (88, 3), from
            :func:`calibrate_background`.
        visualize: If True, also returns an annotated visualization frame.

    Returns:
        If visualize is False: list of 88 binary values (0 or 1).
        If visualize is True: tuple of (binary values, annotated frame,
        metadata dict with keys ``adaptive_threshold``, ``median_distance``,
        ``removed_by_spillover``, ``active_notes``).
    """
    # ------------------------------------------------------------------
    # Phase 1: color-distance sampling (all 88 keys)
    # ------------------------------------------------------------------
    raw_distances: list[float] = []

    for idx, geo in enumerate(KEY_GEOMETRY):
        region = frame[0:1, geo["x_start"]:geo["x_end"]]  # (1, W, 3) BGR
        avg_bgr = np.mean(region.reshape(-1, 3), axis=0)  # (3,)

        distance = float(np.linalg.norm(avg_bgr - background[idx]))
        raw_distances.append(distance)

    # Adaptive threshold: use the per-frame median distance as a baseline.
    # The median tracks background brightness drift (title screens, lighting
    # changes, compression noise) because the majority of keys are unpressed
    # at any given frame.  A key is "pressed" only if its distance exceeds
    # the current baseline by at least COLOR_DISTANCE_THRESHOLD.
    median_distance = float(np.median(raw_distances))
    adaptive_threshold = median_distance + COLOR_DISTANCE_THRESHOLD

    brightness_values: list[int] = [
        1 if d > adaptive_threshold else 0 for d in raw_distances
    ]

    # ------------------------------------------------------------------
    # Phase 2: spillover correction (all keys)
    # ------------------------------------------------------------------
    # For every detected key, check nearby keys (within ±2 positions in
    # PIANO_NOTES order ≈ physically adjacent).  If a neighbor has a
    # substantially higher color distance, this key's detection is likely
    # light spillover from the brighter neighbor rather than a genuine
    # press.
    #
    # The SPILLOVER_RATIO (0.80) preserves chords: two genuinely pressed
    # keys have similar distances (ratio ~1.0 > 0.80), while spillover
    # typically produces only 20–60% of the source's distance.
    removed_by_spillover: list[bool] = [False] * 88

    for i in range(88):
        if brightness_values[i] == 0:
            continue

        # Find the largest distance among detected neighbors within ±2
        max_neighbor_dist = 0.0
        for offset in (-2, -1, 1, 2):
            ni = i + offset
            if 0 <= ni < 88 and brightness_values[ni] == 1:
                if raw_distances[ni] > max_neighbor_dist:
                    max_neighbor_dist = raw_distances[ni]

        # No pressed neighbor → this key is genuine, skip
        if max_neighbor_dist == 0.0:
            continue

        # If this key's distance is much lower than its neighbor → spillover
        if raw_distances[i] < max_neighbor_dist * SPILLOVER_RATIO:
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

        # Dynamic bar scale: threshold at ~25%, genuine beams at 70-100%
        bar_scale = max(adaptive_threshold * 4, 150.0)

        for i, geo in enumerate(KEY_GEOMETRY):
            _draw_key_visualization(
                vis_frame, i,
                geo["x_start"], geo["x_end"],
                raw_distances[i],
                geo["is_black"],
                brightness_values[i] == 1,
                removed_by_spillover[i],
                bar_scale,
            )

        _draw_threshold_lines(vis_frame, adaptive_threshold,
                              median_distance, bar_scale)

        active_notes = [PIANO_NOTES[i] for i in range(88)
                        if brightness_values[i] == 1]
        frame_meta = {
            "adaptive_threshold": adaptive_threshold,
            "median_distance": median_distance,
            "removed_by_spillover": removed_by_spillover,
            "active_notes": active_notes,
        }
        return brightness_values, vis_frame, frame_meta

    return brightness_values


# C-note indices for fixed octave markers (C1–C8).
_C_NOTE_INDICES: set[int] = {3, 15, 27, 39, 51, 63, 75, 87}

# Bar chart zone height in pixels (bottom of frame).
_BAR_ZONE_HEIGHT: int = 150


def _draw_key_visualization(
    vis_frame: NDArray[np.uint8],
    key_index: int,
    x_start: int,
    x_end: int,
    color_distance: float,
    is_black: bool,
    is_detected: bool,
    was_removed: bool,
    bar_scale: float,
) -> None:
    """Draw visualization overlay for a single key onto the frame.

    Args:
        vis_frame: Frame to draw on (modified in place).
        key_index: Index of the current key (0-87).
        x_start: Left pixel boundary of the sampling strip.
        x_end: Right pixel boundary of the sampling strip.
        color_distance: Euclidean BGR distance from background (0–~441).
        is_black: Whether this is a black key.
        is_detected: Whether the key is detected as pressed (after threshold).
        was_removed: Whether this key was removed by spillover correction.
        bar_scale: Distance value that maps to full bar height.
    """
    # Sampling-strip indicator (drawn just below the yellow analysis zone)
    if is_black:
        strip_color = (200, 0, 200)  # magenta for black keys
    else:
        strip_color = (200, 200, 0)  # cyan for white keys
    cv2.rectangle(vis_frame, (x_start, 3), (x_end - 1, 8), strip_color, -1)

    # Color-distance bar at the bottom of the frame
    norm = min(color_distance / bar_scale, 1.0)
    bar_height = int(norm * _BAR_ZONE_HEIGHT)

    # Color by detection state
    if was_removed:
        color = (0, 140, 255)  # orange — spillover removed
    elif is_detected:
        color = (0, 230, 50) if not is_black else (180, 230, 0)  # green / teal
    else:
        color = (60, 60, 60)  # dim gray — below threshold

    bar_top = VIDEO_HEIGHT - bar_height
    cv2.rectangle(vis_frame, (x_start, bar_top), (x_end - 1, VIDEO_HEIGHT),
                  color, -1)

    # Mark spillover-removed keys with a red X
    if was_removed:
        cv2.line(vis_frame, (x_start, bar_top), (x_end - 1, VIDEO_HEIGHT),
                 (0, 0, 255), 2)
        cv2.line(vis_frame, (x_start, VIDEO_HEIGHT), (x_end - 1, bar_top),
                 (0, 0, 255), 2)

    # Label detected keys with their note name
    if is_detected and not was_removed:
        label = PIANO_NOTES[key_index]
        cv2.putText(vis_frame, label,
                    (x_start, bar_top - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, (255, 255, 255), 1)
    # Fixed C-octave markers for orientation (gray, always shown)
    elif key_index in _C_NOTE_INDICES:
        label = PIANO_NOTES[key_index]
        cv2.putText(vis_frame, label,
                    (x_start, VIDEO_HEIGHT - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.25, (120, 120, 120), 1)


def _draw_threshold_lines(
    vis_frame: NDArray[np.uint8],
    adaptive_threshold: float,
    median_distance: float,
    bar_scale: float,
) -> None:
    """Draw dashed threshold and median lines across the bar chart zone."""
    # Threshold line — dashed yellow
    threshold_y = VIDEO_HEIGHT - int(
        min(adaptive_threshold / bar_scale, 1.0) * _BAR_ZONE_HEIGHT
    )
    for x in range(0, VIDEO_WIDTH, 12):
        cv2.line(vis_frame, (x, threshold_y), (min(x + 6, VIDEO_WIDTH), threshold_y),
                 (0, 255, 255), 1)
    cv2.putText(vis_frame, f"threshold ({adaptive_threshold:.0f})",
                (VIDEO_WIDTH - 200, threshold_y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)

    # Median line — dashed dim cyan (noise floor)
    median_y = VIDEO_HEIGHT - int(
        min(median_distance / bar_scale, 1.0) * _BAR_ZONE_HEIGHT
    )
    for x in range(0, VIDEO_WIDTH, 12):
        cv2.line(vis_frame, (x, median_y), (min(x + 6, VIDEO_WIDTH), median_y),
                 (180, 180, 0), 1)
    cv2.putText(vis_frame, f"median ({median_distance:.0f})",
                (VIDEO_WIDTH - 160, median_y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (180, 180, 0), 1)
