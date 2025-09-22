# Light to Sheet

Extract brightness patterns from videos by analyzing 88 vertical slices across each frame.

## Setup

```bash
# Create virtual environment
python -m venv my_env
source my_env/bin/activate  # On Windows: my_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

The program will prompt you for:
1. **Input source** - YouTube URL or local video file
2. **Preview frames** - Save visual previews (recommended for verification)

## How It Works

1. **Video Processing**
   - Downloads YouTube video or loads local file (e.g `downloaded_videos/test.mp4`)
   - Resizes to 1848x1080 (stretches to fit)
   - Converts to 24fps

2. **Frame Analysis**
   - Divides each frame into 88 vertical slices (21px wide)
   - Analyzes the top row of pixels in each slice
   - Calculates brightness percentage (0-100%)

3. **Output**
   - `output.txt` - Brightness values for all frames with timestamps
   - `preview_frames/` - Visual previews showing analysis zones (optional)

## Output Format

Each line in `output.txt` contains:
```
[brightness_array] HH:MM:SS.ffffff
```

Example:
```
[23.5, 45.2, 67.8, ...88 values...] 00:00:01.041667
```

## Files Generated

- `output.txt` - Main results file
- `preview_frames/` - Preview images (every 6 frames)
- `downloaded_videos/` - Cached YouTube downloads for reuse