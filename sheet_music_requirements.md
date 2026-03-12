# Sheet Music Output — Design Spec

> **Status:** Implemented in `src/output_writer.py` (the `OutputWriter._write_sheet_music()` method).

## Requirements

The script shall create an ASCII sheet music output file (`sheet_music.txt`) with the following properties:

- The file represents a **timeline expanding left to right** (not top to bottom).
- Each **column** represents one video frame (at 24fps, so column spacing is 1/24 second = ~0.041667s).
- Each column is sorted in **descending pitch order** (highest notes at top, lowest at bottom). Sorting follows musical pitch rules, not alphabetical order (e.g., C#4 > C4, B3 < C4).
- Silences (no notes playing) are represented by `---`.
- Repeated consecutive notes on the same row are replaced with `---` to indicate sustain.
- All notes are formatted to **exactly 3 characters** for alignment (e.g., `C4 `, `G#3`). This accommodates the longest possible note string like `G#3`.

## Example Output

```
C5  D4  F4  B4  --- D4
D3  --- C4  G#4 --- B3
--- --- --- D4  ---
```

- Column 1 (`C5`, `D3`): frame at 00:00:00.000000
- Column 2 (`D4`): frame at 00:00:00.041667
- And so on.
