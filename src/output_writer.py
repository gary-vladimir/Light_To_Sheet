"""
Output generation functionality for Light to Sheet.

This module handles writing analysis results to multiple output formats:
- output.txt: Raw binary arrays with timestamps
- piano.csv: CSV with piano note headers
- sheet_music.txt: ASCII sheet music notation
"""

from __future__ import annotations

import io
from types import TracebackType

from .config import PIANO_NOTES, SHEET_MUSIC_ROWS
from .utils import format_note_3char, get_note_pitch_value


class OutputWriter:
    """Manages writing output to multiple file formats simultaneously.

    Use as a context manager::

        with OutputWriter("output.txt") as writer:
            writer.write_frame(values, timestamp)
    """

    def __init__(
        self,
        output_file: str = "output.txt",
        piano_csv: str = "piano.csv",
        sheet_music_file: str = "sheet_music.txt",
    ) -> None:
        self.output_file = output_file
        self.piano_csv = piano_csv
        self.sheet_music_file = sheet_music_file
        self.sheet_music_columns: list[list[str]] = []
        self._output_f: io.TextIOWrapper | None = None
        self._csv_f: io.TextIOWrapper | None = None

    def __enter__(self) -> OutputWriter:
        """Open all output files. Cleans up on partial failure."""
        try:
            self._output_f = open(self.output_file, "w")
            self._csv_f = open(self.piano_csv, "w")
        except Exception:
            # If the second open fails, close the first handle
            if self._output_f is not None:
                self._output_f.close()
                self._output_f = None
            raise

        # Write CSV header
        header = "timestamp," + ",".join(PIANO_NOTES) + "\n"
        self._csv_f.write(header)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close files and generate sheet music."""
        if self._output_f is not None:
            self._output_f.close()
        if self._csv_f is not None:
            self._csv_f.close()

        # Only generate sheet music if we have data and no exception occurred
        if exc_type is None and self.sheet_music_columns:
            self._write_sheet_music()

    def write_frame(self, brightness_values: list[int], timestamp_str: str) -> None:
        """Write frame data to all output formats.

        Args:
            brightness_values: List of 88 binary values (0 or 1).
            timestamp_str: Formatted timestamp string.
        """
        assert self._output_f is not None and self._csv_f is not None

        # Raw output
        self._output_f.write(f"{brightness_values} {timestamp_str}\n")
        self._output_f.flush()

        # CSV with piano note columns
        csv_values = ",".join(map(str, brightness_values))
        self._csv_f.write(f"{timestamp_str},{csv_values}\n")
        self._csv_f.flush()

        # Collect active notes for sheet music
        active_notes = [
            PIANO_NOTES[i]
            for i, value in enumerate(brightness_values)
            if value == 1
        ]

        # Sort by pitch, highest first — then fix to exactly 10 rows
        # (a pianist has 10 fingers, so at most 10 simultaneous notes)
        active_notes.sort(key=get_note_pitch_value, reverse=True)
        column = [format_note_3char(n) for n in active_notes[:SHEET_MUSIC_ROWS]]

        # Pad to exactly SHEET_MUSIC_ROWS so every column is the same height
        while len(column) < SHEET_MUSIC_ROWS:
            column.append("---")

        self.sheet_music_columns.append(column)

    def _write_sheet_music(self) -> None:
        """Generate and write ASCII sheet music to file.

        The output has exactly SHEET_MUSIC_ROWS (10) rows — one per finger.
        Row 1 (top) = highest pitch, row 10 (bottom) = lowest pitch.
        Each column = one frame.

        Repeat-suppression rule (column-level):
        - If a column is **identical** to the previous column (every row
          matches), ALL rows in that column are written as '---' (full sustain).
        - If a column **differs** from the previous column in ANY row (a new
          note appeared, a note was released, or notes shifted rows), ALL
          notes in that column are written out — including sustained notes.
        This ensures that when a new note is added while other notes are held,
        the held notes are still visible alongside the new one.
        """
        print("Generating sheet music...")

        # Pre-compute which columns are identical to their predecessor.
        # column_changed[i] is True when column i differs from column i-1.
        num_cols = len(self.sheet_music_columns)
        column_changed: list[bool] = [True] * num_cols  # first column always shown
        for i in range(1, num_cols):
            column_changed[i] = self.sheet_music_columns[i] != self.sheet_music_columns[i - 1]

        with open(self.sheet_music_file, "w") as sheet_f:
            for row_idx in range(SHEET_MUSIC_ROWS):
                row_parts: list[str] = []

                for col_idx, col in enumerate(self.sheet_music_columns):
                    if column_changed[col_idx]:
                        # Column has at least one change — show all notes
                        row_parts.append(col[row_idx])
                    else:
                        # Entire column is identical to previous — sustain
                        row_parts.append("---")

                sheet_f.write(" ".join(row_parts) + "\n")

        print(f"Sheet music saved to: {self.sheet_music_file}")
