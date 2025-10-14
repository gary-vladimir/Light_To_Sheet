# Light to Sheet

Detects piano key presses from videos by analyzing brightness patterns across 88 vertical slices representing the 88 piano keys (A0 to C8). Converts video into binary key states, CSV data, and ASCII sheet music notation.

## Setup

```bash
# Create virtual environment
python -m venv my_env
source my_env/bin/activate  # On Windows: my_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note:** Requires FFmpeg to be installed on your system for video preprocessing.

## Usage

```bash
python main.py
```

The program will prompt you for:
1. **Input source** - Choose between:
   - YouTube URL (automatically downloads and caches)
   - Local video file path (relative or absolute)
2. **Preview frames** - Save visual analysis frames (y/n, default: yes)

## How It Works

1. **Video Preprocessing**
   - Downloads YouTube video (cached in `downloaded_videos/`) or loads local file
   - Uses FFmpeg to resize to 1848x1080 (stretches to fit)
   - Converts to 24fps while maintaining original duration

2. **Frame Analysis**
   - Divides each frame into 88 vertical slices with variable widths (15-33px)
   - Slice widths proportionally match piano key layout
   - Analyzes the top 1px row of each slice for brightness
   - Converts brightness to binary: **1** if >70% (key pressed), **0** otherwise

3. **Output Generation**
   - Generates three synchronized output files
   - Optional visualization frames saved every 6 frames (4 per second)
   - Real-time processing simulation with 1/24 second delays

## Output Files

### `output.txt`
Raw binary arrays representing key states at each frame:
```
[0, 1, 0, 1, 0, ...88 values...] 00:00:01.041667
```
- 88 binary values (0 = key up, 1 = key down)
- Timestamp in HH:MM:SS.ffffff format

### `piano.csv`
Structured CSV with piano note column headers:
```
timestamp,A0,A#0,B0,C1,C#1,D1,D#1,E1,F1,F#1,G1,G#1,A1,...,C8
00:00:00.041667,0,1,0,1,0,0,1,0,0,0,1,0,0,...,0
```
- First row: timestamp + 88 note labels (A0 through C8)
- Each data row: timestamp + 88 binary values

### `sheet_music.txt`
Human-readable ASCII sheet music notation:
```
C5  D#4 ---  G3  A2  ---  C4  ...
A#3 ---  F#2 ---  ---  E3  ---  ...
---  C2  ---  ---  B1  ---  ---  ...
```
- Each column represents one frame
- Multiple rows show simultaneous notes (sorted highest to lowest pitch)
- Active notes shown as 3-character labels (e.g., "C#4", "A0 ", "C8 ")
- Repeated consecutive notes replaced with "---" for clarity
- Silence shown as "---"

### `preview_frames/` (optional)
Visual analysis frames showing:
- Brightness bars for each slice (color-coded)
- Vertical slice divisions
- Frame number and timestamp overlay
- Brightness statistics (average, min, max)
- Saved as JPG images every 6 frames

### `downloaded_videos/`
Cached YouTube downloads for reuse (not deleted between runs)

## Technical Details

- **Piano Key Mapping**: 88 keys from A0 (lowest) to C8 (highest)
- **Variable Slice Widths**: Defined in `vertical_slices` array to match piano proportions
- **Brightness Threshold**: 70% - adjustable in `analyze_frame_brightness()` function (line 209)
- **Frame Rate**: Fixed at 24fps for consistent timing
- **Video Download**: Uses `yt_dlp` library with caching
- **Video Processing**: Uses FFmpeg subprocess for reliable preprocessing
- **Cleanup**: Previous outputs automatically deleted on each run (except cached videos)