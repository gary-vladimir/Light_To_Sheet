"""
Utility functions for Light to Sheet.

This module contains helper functions for:
- Timestamp formatting
- Note formatting and pitch calculation
- File cleanup operations
"""

from __future__ import annotations

import os
import shutil
from datetime import timedelta


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.ffffff format.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string.
    """
    td = timedelta(seconds=seconds)
    total = td.total_seconds()
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:09.6f}"


# Note values within an octave for pitch sorting (C=0 through B=11)
_NOTE_VALUES: dict[str, int] = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}


def get_note_pitch_value(note_str: str) -> int:
    """Convert note string (e.g., 'C#4') to a numeric pitch value for sorting.

    Args:
        note_str: Note string like 'C4' or 'C#4'.

    Returns:
        Numeric pitch value (higher = higher pitch).
    """
    if "#" in note_str:
        note = note_str[:2]
        octave = int(note_str[2:])
    else:
        note = note_str[0]
        octave = int(note_str[1:])

    return octave * 12 + _NOTE_VALUES[note]


def format_note_3char(note_str: str) -> str:
    """Format note to exactly 3 characters for alignment.

    Args:
        note_str: Note string like 'C4' or 'C#4'.

    Returns:
        3-character formatted note string (e.g., 'C4 ' or 'C#4').
    """
    if len(note_str) == 2:  # e.g., 'C4'
        return note_str + " "
    elif len(note_str) == 3:  # e.g., 'C#4'
        return note_str
    else:
        return "---"


def get_downloaded_videos() -> list[str]:
    """Get list of video files from downloaded_videos folder.

    Returns:
        Sorted list of video filenames.
    """
    downloads_dir = "downloaded_videos"

    if not os.path.exists(downloads_dir):
        return []

    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}
    video_files = [
        f for f in os.listdir(downloads_dir)
        if os.path.splitext(f)[1].lower() in video_extensions
    ]

    video_files.sort()
    return video_files


_OUTPUT_FILES: list[str] = ["output.txt", "piano.csv", "sheet_music.txt"]


def cleanup_previous_runs() -> None:
    """Clean up files from previous runs (but keep downloaded videos).

    Removes:
    - preview_frames/ directory
    - output.txt, piano.csv, sheet_music.txt
    """
    if os.path.exists("preview_frames"):
        shutil.rmtree("preview_frames")
        print("Cleaned up previous preview frames")

    for filename in _OUTPUT_FILES:
        if os.path.exists(filename):
            os.remove(filename)
            print(f"Cleaned up previous {filename}")
