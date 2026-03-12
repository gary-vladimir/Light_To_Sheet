# Light to Sheet

Detects piano key presses from Synthesia-style videos by analyzing brightness patterns across 88 vertical slices representing the 88 piano keys (A0 to C8). Converts video into binary key states, CSV data, and ASCII sheet music notation.

Available as both a **web app** and a **CLI tool**.

## Setup

```bash
# Create virtual environment
python -m venv my_env
source my_env/bin/activate  # On Windows: my_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**System requirements:**
- **FFmpeg** — video preprocessing (`brew install ffmpeg` or `apt install ffmpeg`)
- **Deno** — required by yt-dlp for YouTube downloads (`brew install deno` or `curl -fsSL https://deno.land/install.sh | sh`)

## Usage

### Web App

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser. From there you can:

1. Paste a **YouTube URL** or **upload a video file**
2. Click **Process Video**
3. View the ASCII sheet music inline
4. Download `output.txt`, `piano.csv`, and `sheet_music.txt`

### CLI

```bash
python main.py
```

The program will prompt you for:
1. **Input source** — YouTube URL (downloads and caches) or local video file (interactive menu)
2. **Preview frames** — save visual analysis frames (y/n, default: yes)

### DevContainer

The project includes a `.devcontainer/` configuration for one-command setup:

```bash
# Opens in a container with Python 3.11, FFmpeg, and all dependencies pre-installed
# Port 5000 is forwarded automatically for the web app
```

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
   - Optional visualization frames saved every 6 frames (4 per second, CLI only)

## Output Files

### `output.txt`
Raw binary arrays representing key states at each frame:
```
[0, 1, 0, 1, 0, ...88 values...] 00:00:01.041667
```

### `piano.csv`
Structured CSV with piano note column headers:
```
timestamp,A0,A#0,B0,C1,C#1,...,C8
00:00:00.041667,0,1,0,1,0,...,0
```

### `sheet_music.txt`
Human-readable ASCII sheet music notation:
```
C5  D#4 ---  G3  A2  ---  C4  ...
A#3 ---  F#2 ---  ---  E3  ---  ...
---  C2  ---  ---  B1  ---  ---  ...
```
- Each column = one frame (1/24 second)
- Rows = simultaneous notes (highest pitch at top)
- `---` = silence or sustained note

### `preview_frames/` (CLI only)
Annotated visualization frames with brightness bars, slice divisions, and active key counts.

## Project Structure

```
Light_To_Sheet/
├── app.py               # Web app (Flask)
├── main.py              # CLI tool
├── templates/
│   └── index.html       # Web frontend
├── static/
│   └── style.css        # Web styling
├── src/
│   ├── config.py        # Piano constants, video settings
│   ├── utils.py         # Timestamp formatting, note helpers
│   ├── video_downloader.py  # YouTube downloads (yt-dlp)
│   ├── frame_analyzer.py    # Brightness detection (OpenCV)
│   ├── output_writer.py     # Multi-format output generation
│   └── video_processor.py   # FFmpeg preprocessing, frame loop
├── requirements.txt
└── .devcontainer/       # Container config for easy deployment
```

## Technical Details

- **Piano Key Mapping**: 88 keys from A0 (lowest) to C8 (highest)
- **Variable Slice Widths**: Defined in `src/config.py` to match piano proportions
- **Brightness Threshold**: 70% — configurable in `src/config.py`
- **Frame Rate**: Fixed at 24fps (24 frames = 1 second of music)
- **Dependencies**: OpenCV, NumPy, yt-dlp, Flask, FFmpeg
