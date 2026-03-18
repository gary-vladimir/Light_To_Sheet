"""
Piano configuration constants for Light to Sheet.

This module contains all piano-related constants including:
- Key geometry for brightness detection (white/black key sampling regions)
- Note names and octave mapping
- Piano note labels (A0 to C8)
- Video processing settings
"""

from __future__ import annotations

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
VIDEO_WIDTH: int = 1848  # Preprocessed frame width (52 white keys × ~35.54px)
VIDEO_HEIGHT: int = 1080
VIDEO_FPS: int = 24

# Background calibration: number of initial frames used to estimate per-key
# background color.  The median BGR across these frames is the reference.
CALIBRATION_FRAMES: int = 48  # 2 seconds at 24fps

# Detection threshold (adaptive): minimum Euclidean BGR distance ABOVE the
# per-frame median to consider a key "pressed".  The per-frame median tracks
# background drift (title screens, lighting changes, compression noise), so
# this value is the margin above the current noise floor — not an absolute
# distance.  Typical noise spread is 5–15 around the median; dim beams
# start around 30 above the median; bright beams reach 200+ above.
COLOR_DISTANCE_THRESHOLD: float = 30.0

# ---------------------------------------------------------------------------
# Key detection geometry
# ---------------------------------------------------------------------------
# White and black keys are detected separately to avoid spillover between
# adjacent keys.  White keys are evenly spaced across VIDEO_WIDTH; black keys
# sit at the boundaries between adjacent white keys.
NUM_WHITE_KEYS: int = 52
NUM_BLACK_KEYS: int = 36
WHITE_KEY_WIDTH: float = VIDEO_WIDTH / NUM_WHITE_KEYS  # ~35.54px

# Sampling strip widths (pixels) — narrow center strips reduce spillover
WHITE_SAMPLE_WIDTH: int = 20  # center strip for white keys (of ~35.5px zone)
BLACK_SAMPLE_WIDTH: int = 12  # narrow strip for black keys

# Spillover correction: if a detected black key's brightness is less than
# this fraction of its brightest pressed white neighbor, treat it as spillover.
# Spillover typically produces 50–70% of source brightness (ratio 0.53–0.74).
# Genuine presses produce 80–100%+ of neighbor brightness (ratio 0.84+).
SPILLOVER_RATIO: float = 0.80


def _build_key_geometry() -> list[dict]:
    """Pre-compute pixel sampling regions for all 88 piano keys.

    White keys: 52 equal zones of ~35.54px.  Sample the center strip.
    Black keys: centered at the boundary between adjacent white zones.
                Sample a narrow center strip.  Also stores indices of
                white neighbors for the spillover correction pass.

    Returns:
        List of 88 dicts (one per key in PIANO_NOTES order), each with:
          - is_black:  bool
          - x_start:   int — left edge of sampling strip (inclusive)
          - x_end:     int — right edge of sampling strip (exclusive)
          - left_white_idx:  int | None — PIANO_NOTES index of left white neighbor
          - right_white_idx: int | None — PIANO_NOTES index of right white neighbor
    """
    # Step 1: classify keys and assign white-key ordinals (0-51)
    white_ordinal: dict[int, int] = {}  # PIANO_NOTES index → ordinal among whites
    w = 0
    for i, note in enumerate(PIANO_NOTES):
        if "#" not in note:
            white_ordinal[i] = w
            w += 1

    # Step 2: compute geometry for each key
    geometry: list[dict] = []
    for i, note in enumerate(PIANO_NOTES):
        is_black = "#" in note

        if not is_black:
            # White key: center of its equal-width zone
            seq = white_ordinal[i]
            center = (seq + 0.5) * WHITE_KEY_WIDTH
            half = WHITE_SAMPLE_WIDTH / 2
            x_start = max(0, int(round(center - half)))
            x_end = min(VIDEO_WIDTH, int(round(center + half)))
            geometry.append({
                "is_black": False,
                "x_start": x_start,
                "x_end": x_end,
                "left_white_idx": None,
                "right_white_idx": None,
            })
        else:
            # Black key: midpoint between its two white neighbors
            left_idx = i - 1   # always a white key
            right_idx = i + 1  # always a white key
            left_center = (white_ordinal[left_idx] + 0.5) * WHITE_KEY_WIDTH
            right_center = (white_ordinal[right_idx] + 0.5) * WHITE_KEY_WIDTH
            center = (left_center + right_center) / 2
            half = BLACK_SAMPLE_WIDTH / 2
            x_start = max(0, int(round(center - half)))
            x_end = min(VIDEO_WIDTH, int(round(center + half)))
            geometry.append({
                "is_black": True,
                "x_start": x_start,
                "x_end": x_end,
                "left_white_idx": left_idx,
                "right_white_idx": right_idx,
            })

    return geometry


KEY_GEOMETRY: list[dict] = _build_key_geometry()

# Analysis zone (top row of frame)
ANALYSIS_ZONE_HEIGHT: int = 1

# Sheet music output
SHEET_MUSIC_ROWS: int = 10  # Fixed row count — a pianist has 10 fingers

# Preview frame settings
PREVIEW_SAVE_INTERVAL: int = 6  # Save every 6th frame (4 previews per second at 24fps)
