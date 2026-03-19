# Light to Sheet

Detects piano key presses from Synthesia-style videos by measuring color distance from a calibrated background across 88 sampling strips representing the 88 piano keys (A0 to C8). Converts video into binary key states, CSV data, and ASCII sheet music notation.

**Live app:** [light-to-sheet-2032166340.us-central1.run.app](https://light-to-sheet-2032166340.us-central1.run.app/)

Available as a **web app** (`app.py`), a **CLI tool** (`main.py`), and a **deployed cloud service** (Google Cloud Run). All share the same processing engine in `src/`.

## Setup

### System Requirements

These must be installed on the host machine (or are pre-installed in the DevContainer):

- **Python 3.11+**
- **FFmpeg** — video preprocessing (`brew install ffmpeg` or `apt install ffmpeg`)
- **Deno >= 2.0** — required by yt-dlp for YouTube downloads (`brew install deno`)

### Python Dependencies

```bash
# Create virtual environment
python -m venv my_env
source my_env/bin/activate  # On Windows: my_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### DevContainer (recommended for consistent environments)

The project includes a `.devcontainer/` configuration that installs Python 3.11, FFmpeg, Deno, and all pip dependencies automatically. Port 5000 is forwarded for the web app.

```bash
# VS Code: Ctrl+Shift+P → "Dev Containers: Reopen in Container"
# Then run: DEBUG=1 python app.py (web) or python main.py (CLI)
```

## Usage

### Web App (local)

```bash
DEBUG=1 python app.py
```

Opens on [http://localhost:5000](http://localhost:5000). The `DEBUG=1` flag disables Firebase auth for local development.

From the browser:
1. **Upload a video file** (max 500 MB) or paste a **YouTube URL**
2. Click **Process Video** and wait (processing is fast — no real-time delay)
3. View the ASCII sheet music inline in the browser
4. Download `output.txt`, `piano.csv`, and `sheet_music.txt`

### Web App (production)

The app is deployed on Google Cloud Run with Firebase Google Sign-In. See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions.

YouTube URL downloads in production are routed through a Mac-based proxy (residential IP). See [DOWNLOAD_PROXY_SETUP.md](DOWNLOAD_PROXY_SETUP.md) for setup.

### CLI

```bash
python main.py
```

The CLI prompts for:
1. **Input source** — YouTube URL (downloads and caches in `downloaded_videos/`) or local video file (interactive arrow-key menu via `inquirer`)
2. **Preview frames** — save annotated visualization frames to `preview_frames/` (y/n, default: yes)

The CLI runs in **real-time mode** (1/24 second delay per frame), so processing takes as long as the video's duration. Output files are written to the current directory.

## Web App API

### `GET /`
Serves the single-page frontend.

### `POST /api/process`
**Requires authentication** (Firebase ID token in `Authorization: Bearer <token>` header).

Accepts multipart form data with either:
- `youtube_url` (string) — a YouTube video URL, or
- `video_file` (file) — an uploaded video file (max 500 MB)

Returns JSON:
```json
{
  "job_id": "uuid",
  "sheet_music": "G5  --- B4  ...\nD5  --- ---  ...",
  "files": ["output.txt", "piano.csv", "sheet_music.txt"],
  "preview_frames": ["frame_000006.jpg", "frame_000012.jpg", "..."]
}
```

Each request gets an isolated job directory under the system temp folder (`/tmp/light_to_sheet_jobs/<uuid>/`). The preprocessed and uploaded video files are cleaned up after processing; only the three output files remain for download.

### `GET /api/download/<job_id>/<filename>`
Serves an output file for download. Only `output.txt`, `piano.csv`, and `sheet_music.txt` are allowed (whitelist). The job ID is validated as a UUID to prevent path traversal.

### `GET /api/preview/<job_id>/<filename>`
Serves a preview frame image. Filename must match `frame_NNNNNN.jpg`. The job ID is validated as a UUID and the filename is checked against a regex pattern to prevent path traversal.

## How It Works

### 1. Video Preprocessing (FFmpeg)
- Downloads YouTube video (cached in `downloaded_videos/`) or accepts a local/uploaded file
- Uses FFmpeg to resize to **1848x1080** (stretches to fit, no aspect ratio preservation)
- Converts to **24fps** while maintaining original duration
- Width of 1848px is intentional — 52 white keys × ~35.54px each

### 2. Frame Analysis (OpenCV)
- **Background calibration**: reads the first 48 frames (2 seconds) and computes the median BGR color for each of the 88 key sampling regions — this establishes what "no beam" looks like per key
- Divides frame into **88 sampling strips** — 52 white-key center strips (20px) and 36 black-key boundary strips (12px)
- Samples the **top 1px row** of each strip and computes **Euclidean color distance** from the calibrated background
- **Adaptive per-frame threshold**: computes the median distance across all 88 keys each frame (tracks background drift from title screens, lighting changes, compression noise), then detects a key as pressed only if its distance exceeds `median + COLOR_DISTANCE_THRESHOLD(30)`
- **All-key spillover correction**: for each detected key, checks neighbors within ±2 positions in piano order — if the key's distance is less than 80% of its brightest neighbor's distance, the detection is removed as light spillover (preserves chords where both keys have similar distances)
- This approach detects beams of **any color or brightness** — not just bright/white beams. Orange, blue, green, or dim beams that grayscale detection would miss are all correctly identified

### 3. Output Generation
Three synchronized output files are written per run:
- `output.txt` — raw binary arrays with timestamps
- `piano.csv` — CSV with 88 note-name column headers
- `sheet_music.txt` — ASCII sheet music (columns = time, rows = simultaneous notes)

### Web vs CLI Differences

| Behavior | Web (`app.py`) | CLI (`main.py`) |
|---|---|---|
| Processing speed | As fast as possible (`realtime=False`) | Real-time pacing (`realtime=True`) |
| Preview frames | Enabled (served via API for in-browser navigation) | Optional (saves to `preview_frames/`) |
| Output location | Temp job directory (`/tmp/.../<uuid>/`) | Current working directory |
| Input method | YouTube URL or file upload via browser | YouTube URL or local file via terminal prompts |

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
timestamp,A0,A#0,B0,C1,C#1,...,C8
00:00:00.041667,0,1,0,1,0,...,0
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
- Each column = one frame (1/24 second)
- Exactly 10 rows (one per finger — at most 10 simultaneous notes)
- Rows = simultaneous notes (highest pitch at top, lowest at bottom)
- All notes are exactly 3 characters wide for alignment (e.g., `C4 `, `C#4`)
- Column-level repeat suppression: if an entire column is identical to the previous one, all rows show `---` (sustain). If any note changed (added/removed), all notes in that column are shown — including sustained ones
- Silence = `---`

See `sheet_music_requirements.md` for the original design spec.

### `preview_frames/`
Annotated visualization frames with a rich detection overlay:

**Bar chart (bottom of frame)** — one bar per key, height proportional to color distance:
- **Green bars** — detected white keys (pressed)
- **Teal bars** — detected black keys (pressed)
- **Orange bars + red X** — keys removed by spillover correction
- **Dim gray bars** — undetected keys (below threshold)
- **Dashed yellow line** — adaptive detection threshold for this frame
- **Dashed cyan line** — per-frame median distance (noise floor)

**Sampling strip indicators (top of frame)**:
- Cyan strips = white key sampling regions (20px)
- Magenta strips = black key sampling regions (12px)

**Key labels**:
- Detected keys are labeled with their note name (e.g., "C4", "F#5")
- C-octave markers (C1–C8) shown in gray for orientation

**Info panel (top-left corner)**:
- Frame number and timestamp
- Active key count, adaptive threshold value, and median distance
- List of currently detected note names (green)
- Spillover removal count (orange, shown only when > 0)

**Saving**:
- Saved as JPG images every 6 frames (4 per second at 24fps)
- In the **web app**, preview frames are browsable with prev/next arrow buttons and keyboard arrow keys
- In the **CLI**, preview frames are saved to `preview_frames/` on disk

## Project Structure

```
Light_To_Sheet/
├── app.py                       # Web app entry point (Flask + Firebase Auth)
├── main.py                      # CLI entry point
├── download_proxy.py            # Mac-side YouTube download proxy server
├── Dockerfile                   # Production Docker image (Cloud Run)
├── .dockerignore                # Files excluded from Docker build
├── requirements.txt             # Python dependencies
│
├── templates/
│   └── index.html               # Single-page frontend (Firebase Auth + vanilla JS)
├── static/
│   └── style.css                # Dark theme UI with animations
│
├── src/                         # Shared processing engine
│   ├── __init__.py              # Package marker (v1.0.0)
│   ├── config.py                # All constants: key geometry, note mapping, detection thresholds
│   ├── utils.py                 # Timestamp formatting, note pitch sorting, file cleanup
│   ├── video_downloader.py      # YouTube downloads (proxy in production, yt-dlp locally)
│   ├── frame_analyzer.py        # Per-frame color-distance detection, adaptive threshold, spillover correction, visualization (OpenCV)
│   ├── output_writer.py         # Multi-format file writer (context manager)
│   └── video_processor.py       # FFmpeg preprocessing + frame-by-frame loop
│
├── DEPLOYMENT.md                # Full Cloud Run deployment guide
├── DOWNLOAD_PROXY_SETUP.md      # YouTube download proxy setup (Cloudflare Tunnel)
├── sheet_music_requirements.md  # Original design spec for ASCII sheet music
│
├── .devcontainer/
│   ├── Dockerfile               # Dev environment: Python 3.11 + FFmpeg + Deno
│   └── devcontainer.json        # VS Code / Codespaces config, forwards port 5000
└── .gitignore
```

## Configuration

All tunables live in `src/config.py`:

| Constant | Value | Description |
|---|---|---|
| `VIDEO_WIDTH` | 1848 | Preprocessed frame width (52 white keys x ~35.54px) |
| `VIDEO_HEIGHT` | 1080 | Frame height after preprocessing |
| `VIDEO_FPS` | 24 | Target frame rate (24 frames = 1 second) |
| `CALIBRATION_FRAMES` | 48 | Frames used to estimate per-key background color (2 sec) |
| `COLOR_DISTANCE_THRESHOLD` | 30.0 | Margin above per-frame median distance to consider a key "pressed" (adaptive) |
| `WHITE_SAMPLE_WIDTH` | 20 | Center strip width for white key sampling (of ~35.5px zone) |
| `BLACK_SAMPLE_WIDTH` | 12 | Narrow strip width for black key sampling |
| `SPILLOVER_RATIO` | 0.80 | Any key must be >= 80% of its brightest neighbor's distance to be kept |
| `SHEET_MUSIC_ROWS` | 10 | Fixed row count for sheet music (one per finger) |
| `PREVIEW_SAVE_INTERVAL` | 6 | Save a preview frame every N frames |
| `PIANO_NOTES` | 88 strings | Note labels from A0 to C8 |

## Technical Details

- **Piano Key Mapping**: 88 keys from A0 (lowest) to C8 (highest), generated by `generate_piano_notes()` in `config.py`
- **Background Calibration**: The first 48 frames (2 seconds at 24fps) are read to establish per-key background colors. The **median** BGR color is computed across these frames for each key's sampling strip — the median is robust to outliers (keys that happen to be pressed during calibration)
- **Color Distance Detection**: Each frame computes Euclidean BGR distance from the calibrated background for all 88 keys. This detects beams of **any color or brightness** — orange beams (which produce only ~68% grayscale brightness, invisible to traditional brightness thresholds) register distances of 250+ and are clearly detected
- **Adaptive Threshold**: The per-frame **median distance** across all 88 keys serves as a floating baseline that tracks background drift (title screens fading in, lighting changes, compression noise). A key is "pressed" only if `distance > median + 30`. This prevents false-positive bursts during video transitions where the background brightness shifts
- **Key Geometry**: White keys (52) are sampled at narrow 20px center strips within equal-width zones (~35.5px each). Black keys (36) are sampled at narrow 12px strips centered on the boundary between adjacent white keys. The narrow strips minimize spillover contamination from neighboring key beams
- **All-Key Spillover Correction**: For every detected key, its distance is compared against its strongest neighbor within ±2 positions (physically adjacent keys). If the key's distance is less than 80% of the neighbor's distance, it is removed as light spillover. This preserves chords (two genuinely pressed keys have similar distances, ratio ~1.0 > 0.80) while removing spillover (dim reflected light at 20–60% of the source's distance)
- **Frame Rate Normalization**: All videos are converted to 24fps during preprocessing, so frame count maps directly to time (24 frames = 1 second)
- **YouTube Downloads**: In production, YouTube downloads are routed through a Mac-based proxy (`download_proxy.py`) via Cloudflare Tunnel — YouTube blocks all cloud server IPs, so a residential IP is required. Locally, yt-dlp downloads directly (requires Deno as JS runtime). Videos are cached to avoid re-downloading
- **Web App Auth**: Firebase Authentication with Google Sign-In. The frontend obtains a Firebase ID token and sends it in the `Authorization` header. The backend verifies it via `firebase-admin`. Auth is disabled in local dev when credentials aren't configured
- **Web App Jobs**: Each web request creates an isolated temp directory (`/tmp/light_to_sheet_jobs/<uuid>/`), processes there, and serves files for download. Preprocessed/uploaded videos are cleaned up after processing
