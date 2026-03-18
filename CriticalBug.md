# Critical Bug: Key Spillover (RESOLVED)

> **Status**: Resolved in the `black-keys-bug` branch. The solution below was implemented and extended beyond the original proposal.

## Original Problem

The old detection system used contiguous vertical slices of varying width (`VERTICAL_SLICES`) that assumed light beams don't overlap neighboring keys. This worked for white keys but **completely failed for black keys**, which sit physically between two white keys.

**Example**: A light beam on C#4 (black key) spills over onto its neighbors C4 and D4 (white keys), causing three false detections instead of one. The same happens in reverse — a white key beam spills onto adjacent black keys.

## Implemented Solution

The fix replaced the entire detection pipeline with three major changes:

### 1. Separate Key Geometry (replaces `VERTICAL_SLICES`)

Instead of contiguous slices, each key now has a **narrow center sampling strip** that avoids the overlap zones:

- **White keys (52)**: 20px strips centered within equal-width ~35.5px zones
- **Black keys (36)**: 12px strips centered on the boundary between adjacent white key zones

The narrow strips sample only the core of each key's beam, minimizing contamination from neighboring keys. Pre-computed in `KEY_GEOMETRY` in `config.py`.

### 2. Color Distance Detection (replaces grayscale brightness)

The old approach converted frames to grayscale and checked brightness > 70%. This failed for:
- Orange beams (~68% grayscale, below the 70% threshold)
- Dark-colored beams (e.g., dark blue converts to very low grayscale)
- Color changes mid-video

The new approach:
1. **Calibrates background** from the first 48 frames — computes median BGR per key
2. **Measures Euclidean color distance** from background for each key each frame
3. Uses an **adaptive per-frame threshold**: `median_distance + 30` — the median tracks background drift (title screens, transitions, compression noise), preventing false-positive bursts

### 3. All-Key Spillover Correction (extends the original proposal)

The original proposal only addressed black key spillover. The implemented solution corrects spillover on **all 88 keys**:

- For every detected key, check neighbors within **±2 positions** in piano order
- If the key's distance is less than **80%** of its brightest neighbor's distance, remove it as spillover
- **Preserves chords**: two genuinely pressed keys have similar distances (ratio ~1.0 > 0.80), so neither is removed
- **Removes spillover**: reflected light typically produces only 20–60% of the source beam's distance

This handles all spillover cases:
- Black key spilling onto white neighbors
- White key spilling onto black neighbors
- White key spilling onto adjacent white keys (e.g., at B-C and E-F boundaries)

## Key Files Modified

- `src/config.py` — replaced `VERTICAL_SLICES` with `KEY_GEOMETRY`, added calibration/threshold/spillover constants
- `src/frame_analyzer.py` — complete rewrite: background calibration, color distance detection, adaptive threshold, all-key spillover correction, rich visualization overlay
- `src/video_processor.py` — calls `calibrate_background()` before frame loop, passes background to analysis, passes detection metadata to preview save
