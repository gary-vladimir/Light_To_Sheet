"""
Piano configuration constants for Light to Sheet.

This module contains all piano-related constants including:
- Vertical slice widths for 88 piano keys
- Note names and octave mapping
- Piano note labels (A0 to C8)
- Video processing settings
"""

from __future__ import annotations

# Piano key slice widths (88 keys total)
# These represent the pixel widths for each vertical slice.
# Pattern: white keys are wider (28-33px), black keys are narrower (15-21px)
_OCTAVE_PATTERN: list[int] = [28, 15, 21, 15, 28, 28, 15, 20, 15, 21, 15, 28]
VERTICAL_SLICES: list[int] = [29, 15, 28] + (_OCTAVE_PATTERN * 7) + [33]

# Musical note names (12-note chromatic scale)
CHROMATIC_SCALE: list[str] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Note names for the 88 piano keys (starting from A0)
# Piano starts at A0, so the first 3 notes are A, A#, B before the first full octave
SLICES_TAGS: list[str] = ["A", "A#", "B"] + (CHROMATIC_SCALE * 7) + ["C"]


def generate_piano_notes() -> list[str]:
    """Generate piano note labels with octave numbers (A0 to C8).

    The piano starts at A0. Octaves increment at each C note,
    so the sequence is: A0, A#0, B0, C1, C#1, ..., B7, C8.
    """
    piano_notes: list[str] = []
    octave = 0

    for i, note in enumerate(SLICES_TAGS):
        if note == "C" and i > 0:
            octave += 1
        piano_notes.append(f"{note}{octave}")

    return piano_notes


# Pre-generate piano notes for import
PIANO_NOTES: list[str] = generate_piano_notes()

# Video processing configuration
VIDEO_WIDTH: int = 1848  # Must match sum of VERTICAL_SLICES
VIDEO_HEIGHT: int = 1080
VIDEO_FPS: int = 24

# Brightness detection threshold (percentage, 0-100)
BRIGHTNESS_THRESHOLD: int = 70

# Analysis zone (top row of frame)
ANALYSIS_ZONE_HEIGHT: int = 1

# Sheet music output
SHEET_MUSIC_ROWS: int = 10  # Fixed row count — a pianist has 10 fingers

# Preview frame settings
PREVIEW_SAVE_INTERVAL: int = 6  # Save every 6th frame (4 previews per second at 24fps)
