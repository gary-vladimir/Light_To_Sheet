# Sheet Music Output — Design Spec

> **Status:** Implemented in `src/output_writer.py` (the `OutputWriter._write_sheet_music()` method).

## Requirements

The script shall create an ASCII sheet music output file (`sheet_music.txt`) with the following properties:

- The file represents a **timeline expanding left to right** (not top to bottom).
- Each **column** represents one video frame (at 24fps, so column spacing is 1/24 second = ~0.041667s).
- Each column is sorted in **descending pitch order** (highest notes at top, lowest at bottom). Sorting follows musical pitch rules, not alphabetical order (e.g., C#4 > C4, B3 < C4).
- Silences (no notes playing) are represented by `---`.
- Exactly **10 rows** per output (one per finger — a pianist has at most 10 simultaneous notes). Unused rows are filled with `---`.
- All notes are formatted to **exactly 3 characters** for alignment (e.g., `C4 `, `G#3`). This accommodates the longest possible note string like `G#3`.

### Repeat-suppression (column-level)

Suppression operates on **entire columns**, not individual rows:

- If a column is **identical** to the previous column (every row matches), all rows are replaced with `---` (full sustain).
- If a column **differs** from the previous column in **any** row (a new note appeared, a note was released, or notes shifted), **all** notes in that column are written out — including notes that are sustained from the previous column.

This ensures that when a new note is added while other notes are held, the held notes remain visible alongside the new one.

## Example Output

```
E5  --- E5  --- ---
--- --- F#3 --- ---
--- --- --- --- ---
...  (10 rows total)
```

- Column 1: E5 starts playing → shown.
- Column 2: E5 still held, nothing changed → entire column is `---` (sustain).
- Column 3: E5 still held, but F#3 is newly added → column changed, so **both** E5 and F#3 are shown.
- Columns 4–5: same notes held, no changes → `---` (sustain).
