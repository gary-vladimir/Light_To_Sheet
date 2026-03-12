"""
Frame analysis functionality for Light to Sheet.

This module handles analyzing video frames to detect piano key presses
by measuring brightness across 88 vertical slices.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from .config import (
    BRIGHTNESS_THRESHOLD,
    VERTICAL_SLICES,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)


def analyze_frame_brightness(
    frame: NDArray[np.uint8],
    visualize: bool = False,
) -> list[int] | tuple[list[int], NDArray[np.uint8]]:
    """Analyze brightness using variable-width vertical slices at the top of the frame.

    Each of the 88 slices corresponds to a piano key. The top 1px row of each
    slice is sampled; if average brightness exceeds the threshold the key is
    considered pressed (1), otherwise not (0).

    Args:
        frame: BGR video frame (numpy array).
        visualize: If True, also returns an annotated visualization frame.

    Returns:
        If visualize is False: list of 88 binary values (0 or 1).
        If visualize is True: tuple of (binary values, annotated frame).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness_values: list[int] = []

    vis_frame: NDArray[np.uint8] | None = None
    if visualize:
        vis_frame = frame.copy()
        cv2.rectangle(vis_frame, (0, 0), (VIDEO_WIDTH, 1), (0, 255, 255), 2)

    x_position = 0
    for i, slice_width in enumerate(VERTICAL_SLICES):
        x_start = x_position
        x_end = min(x_position + slice_width, VIDEO_WIDTH)

        slice_region = gray[0:1, x_start:x_end]
        avg_brightness = float(np.mean(slice_region))
        brightness_pct = (avg_brightness / 255.0) * 100.0
        brightness_binary = 1 if brightness_pct > BRIGHTNESS_THRESHOLD else 0
        brightness_values.append(brightness_binary)

        if vis_frame is not None:
            _draw_slice_visualization(vis_frame, i, x_start, x_end, brightness_pct)

        x_position = x_end

    if vis_frame is not None:
        return brightness_values, vis_frame
    return brightness_values


def _draw_slice_visualization(
    vis_frame: NDArray[np.uint8],
    slice_index: int,
    x_start: int,
    x_end: int,
    brightness_pct: float,
) -> None:
    """Draw visualization overlay for a single slice onto the frame.

    Args:
        vis_frame: Frame to draw on (modified in place).
        slice_index: Index of the current slice (0-87).
        x_start: Left pixel boundary of the slice.
        x_end: Right pixel boundary of the slice.
        brightness_pct: Brightness percentage (0-100).
    """
    color_intensity = int(brightness_pct * 2.55)
    color = (0, color_intensity, 255 - color_intensity)

    # Vertical divider between slices
    if slice_index > 0:
        cv2.line(vis_frame, (x_start, 0), (x_start, 50), (100, 100, 100), 1)

    # Brightness bar at the bottom of the frame
    bar_height = int(brightness_pct * 1.5)  # Scale to max ~150px
    cv2.rectangle(
        vis_frame,
        (x_start, VIDEO_HEIGHT - bar_height),
        (x_end - 1, VIDEO_HEIGHT),
        color,
        -1,
    )

    # Label every 11th slice to avoid clutter
    if slice_index % 11 == 0:
        cv2.putText(
            vis_frame,
            f"{brightness_pct:.0f}",
            (x_start + 2, VIDEO_HEIGHT - bar_height - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            (255, 255, 255),
            1,
        )
