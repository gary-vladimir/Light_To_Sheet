# Light to Sheet - Piano Note Detection from Video
"""
This program analyzes videos to detect piano key presses by extracting brightness patterns
across 88 vertical slices (representing the 88 keys of a piano from A0 to C8).
Run as: python main.py

Workflow:
1. User is prompted to choose input source:
   - Option 1: YouTube URL (downloads and caches video)
   - Option 2: Local video file path
2. User chooses whether to save preview frames (optional visualization)
3. Video preprocessing using FFmpeg:
   - Resizes to 1848x1080 (stretch to fit, no aspect ratio preservation)
   - Width is 1848px to accommodate 88 variable-width slices (ranging from 15-33px)
   - Converts to 24fps while maintaining original speed/duration
4. Each frame is processed sequentially:
   a. Convert frame to grayscale
   b. Divide frame into 88 vertical slices with variable widths matching piano key proportions
   c. For each slice, analyze a 1px tall zone at the top of the frame
   d. Calculate average brightness (mean of pixel values 0-255)
   e. Convert to binary: 1 if brightness > 70%, else 0 (detects "key pressed" state)
5. Generate three output files simultaneously:
   - output.txt: Binary arrays with timestamps
   - piano.csv: Timestamped data with piano note headers (A0 to C8)
   - sheet_music.txt: ASCII sheet music notation with note names
6. Optional: Save visualization frames to preview_frames/ directory (every 6 frames)
7. Sleep 1/24 seconds between frames (simulates real-time processing)

Output Files:
- output.txt: Raw binary arrays per frame
  Format: "[0, 1, 0, 1, ...] HH:MM:SS.ffffff"
  - 88 binary values (0 or 1) representing key states

- piano.csv: Structured data with note labels
  Header: "timestamp,A0,A#0,B0,C1,C#1,...,C8"
  Data rows: "HH:MM:SS.ffffff,0,1,0,1,..."

- sheet_music.txt: Human-readable sheet music
  - Multiple rows showing simultaneous notes
  - Notes sorted by pitch (highest to lowest)
  - Repeated consecutive notes replaced with "---" for clarity
  - Format: "C5  D#4 ---  G3  ..." (one column per frame)

- preview_frames/ (optional): Visual analysis frames
  - Saved every 6 frames (4 per second at 24fps)
  - Shows brightness bars, slice divisions, and frame metadata

Technical Notes:
- Uses yt_dlp for YouTube downloads with caching in downloaded_videos/
- Uses FFmpeg for reliable video preprocessing (avoids H.264 decoding errors)
- Variable slice widths defined in 'vertical_slices' array (88 values)
- Piano note mapping: A0 to C8 (88 keys) defined in 'piano_notes' array
- Binary threshold: brightness > 70% = key pressed (1), else not pressed (0)
- Brightness = mean(grayscale_pixel_values) / 255 * 100
- Previous run outputs are cleaned up automatically (but cached videos are kept)
"""

helper = [28,15,21,15,28,28,15,20,15,21,15,28]
vertical_slices = [29,15,28] + (helper*7) + [33]
tags = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
slices_tags = ["A", "A#", "B"] + (tags*7) + ["C"]

# Generate piano notes with octave numbers (A0 to C8)
piano_notes = []
octave = 0  # Start at octave 0 for A0
for i, note in enumerate(slices_tags):
    # First three notes are A0, A#0, B0
    if i == 0:
        octave = 0
    # After B, we go to C1 (new octave starts at C)
    elif note == "C" and i == 3:
        octave = 1
    # Increment octave every time we hit a new C
    elif note == "C" and i > 3:
        octave += 1
    piano_notes.append(f"{note}{octave}")

import cv2
import numpy as np
import yt_dlp
import os
import time
import tempfile
from datetime import timedelta

def get_note_pitch_value(note_str):
    """Convert note string (e.g., 'C#4') to a numeric pitch value for sorting"""
    # Parse note and octave
    if '#' in note_str:
        note = note_str[:2]  # e.g., 'C#'
        octave = int(note_str[2:])
    else:
        note = note_str[0]  # e.g., 'C'
        octave = int(note_str[1:])

    # Note values within an octave (C=0, C#=1, D=2, etc.)
    note_values = {
        'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
        'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
    }

    # Calculate absolute pitch value
    return octave * 12 + note_values[note]

def format_note_3char(note_str):
    """Format note to exactly 3 characters for alignment"""
    if len(note_str) == 2:  # e.g., 'C4'
        return note_str + ' '
    elif len(note_str) == 3:  # e.g., 'C#4'
        return note_str
    else:
        return '---'  # Fallback for unexpected format

def download_youtube_video(url):
    """Download YouTube video and save locally for reuse"""
    print(f"Downloading video from: {url}")

    # Create downloads directory if it doesn't exist
    downloads_dir = 'downloaded_videos'
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)

    # Extract video ID from URL for filename
    video_id = None
    if 'youtube.com/watch?v=' in url:
        video_id = url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[1].split('?')[0]

    if not video_id:
        video_id = 'video'

    output_path = os.path.join(downloads_dir, f'{video_id}.mp4')

    # Check if already downloaded
    if os.path.exists(output_path):
        print(f"Video already downloaded: {output_path}")
        return output_path

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    print(f"Video downloaded and saved to: {output_path}")
    return output_path

def preprocess_video(input_path, output_path):
    """Resize video to 1848x1080 and convert to 24fps using FFmpeg"""
    print("Preprocessing video...")

    # Use FFmpeg directly for more reliable preprocessing
    # This avoids frame seeking issues that cause H.264 decoding errors
    import subprocess

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', input_path,
        '-vf', 'scale=1848:1080:force_original_aspect_ratio=disable,fps=24',  # Resize and set fps
        '-c:v', 'libx264',  # Use H.264 codec
        '-preset', 'fast',  # Fast encoding
        '-crf', '23',  # Quality setting
        '-an',  # No audio
        '-loglevel', 'error',  # Only show errors
        output_path
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)

        # Verify the output
        cap = cv2.VideoCapture(output_path)
        if not cap.isOpened():
            raise Exception("Failed to open preprocessed video")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        print(f"Video preprocessed: {frame_count} frames at {fps}fps ({width}x{height})")
        return output_path

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr}")
        raise Exception(f"Video preprocessing failed: {e.stderr}")
    except Exception as e:
        raise Exception(f"Video preprocessing failed: {str(e)}")

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS.ffffff format"""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    seconds = td.total_seconds() % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:09.6f}"

def analyze_frame_brightness(frame, visualize=False):
    """Analyze brightness using variable width vertical slices at the top of the frame"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    brightness_values = []

    # Create visualization if requested
    if visualize:
        vis_frame = frame.copy()
        # Draw analysis zone boundary (top row)
        cv2.rectangle(vis_frame, (0, 0), (1848, 1), (0, 255, 255), 2)

    # Process each slice with its specific width
    x_position = 0
    for i, slice_width in enumerate(vertical_slices):
        x_start = x_position
        x_end = x_position + slice_width

        # Ensure we don't go beyond frame width
        if x_end > 1848:
            x_end = 1848

        slice_region = gray[0:1, x_start:x_end]

        avg_brightness = np.mean(slice_region)
        brightness_percentage = (avg_brightness / 255.0) * 100.0
        brightness_binary = 1 if brightness_percentage > 70 else 0
        brightness_values.append(brightness_binary)

        if visualize:
            # Color code each slice based on brightness
            color_intensity = int(brightness_percentage * 2.55)
            color = (0, color_intensity, 255 - color_intensity)  # Blue to green gradient

            # Draw vertical lines to show slices
            if i > 0:
                cv2.line(vis_frame, (x_start, 0), (x_start, 50), (100, 100, 100), 1)

            # Draw brightness indicator bar at bottom
            bar_height = int(brightness_percentage * 1.5)  # Scale to max 150px
            cv2.rectangle(vis_frame, (x_start, 1080 - bar_height),
                         (x_end - 1, 1080), color, -1)

            # Add brightness value text for selected slices
            if i % 11 == 0:  # Show every 11th value to avoid clutter
                cv2.putText(vis_frame, f"{brightness_percentage:.0f}",
                           (x_start + 2, 1080 - bar_height - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)

        x_position = x_end

    if visualize:
        return brightness_values, vis_frame
    return brightness_values

def process_video(video_path, output_file, save_previews=True):
    """Process video frames and extract brightness data"""
    print("Processing video frames...")

    # Create preview directory if saving previews
    if save_previews:
        preview_dir = "preview_frames"
        if not os.path.exists(preview_dir):
            os.makedirs(preview_dir)
        print(f"Saving preview frames to: {preview_dir}/")
        print("Preview frames will be saved every 6 frames (4 previews per second)")

    cap = cv2.VideoCapture(video_path)

    # Disable OpenCV's error messages for better output
    cv2.setLogLevel(0)

    fps = 24.0
    frame_duration = 1.0 / fps
    frame_number = 0
    failed_frames = 0

    # Create CSV file with piano note headers and sheet music file
    piano_csv = 'piano.csv'
    sheet_music_file = 'sheet_music.txt'

    # Initialize sheet music data structure - list of columns (frames)
    sheet_music_columns = []

    with open(output_file, 'w') as f, open(piano_csv, 'w') as csv_f:
        # Write CSV header
        header = "timestamp," + ",".join(piano_notes) + "\n"
        csv_f.write(header)
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Check if frame is valid
            if frame is None or frame.size == 0:
                print(f"Warning: Skipping corrupted frame {frame_number}")
                failed_frames += 1
                frame_number += 1
                continue

            # Analyze frame with visualization if saving previews
            if save_previews:
                brightness_values, vis_frame = analyze_frame_brightness(frame, visualize=True)

                # Add frame info to visualization
                timestamp = frame_number * frame_duration
                timestamp_str = format_timestamp(timestamp)
                info_text = f"Frame: {frame_number} | Time: {timestamp_str}"
                cv2.putText(vis_frame, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                # Add brightness stats
                avg_brightness = sum(brightness_values) / len(brightness_values)
                stats_text = f"Avg Brightness: {avg_brightness:.1f}% | Min: {min(brightness_values):.1f}% | Max: {max(brightness_values):.1f}%"
                cv2.putText(vis_frame, stats_text, (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

                # Save preview frame every 6 frames (4 times per second)
                if frame_number % 6 == 0:
                    preview_path = os.path.join(preview_dir, f"frame_{frame_number:06d}.jpg")
                    cv2.imwrite(preview_path, vis_frame)
                    if frame_number % 24 == 0:  # Only print every second to reduce console spam
                        print(f"Saved preview: {preview_path}")
            else:
                brightness_values = analyze_frame_brightness(frame)

            timestamp = frame_number * frame_duration
            timestamp_str = format_timestamp(timestamp)

            output_line = f"{brightness_values} {timestamp_str}"

            # Print abbreviated output (show every 24th frame to reduce console spam)
            if frame_number % 24 == 0:
                print(f"Frame {frame_number}: {output_line[:50]}... {timestamp_str}")

            f.write(output_line + '\n')
            f.flush()

            # Write to CSV with piano notes
            csv_line = f"{timestamp_str}," + ",".join(map(str, brightness_values)) + "\n"
            csv_f.write(csv_line)
            csv_f.flush()

            # Build sheet music column for this frame
            active_notes = []
            for i, value in enumerate(brightness_values):
                if value == 1:  # Note is active
                    active_notes.append(piano_notes[i])

            # Sort notes by pitch (highest to lowest for display)
            active_notes.sort(key=get_note_pitch_value, reverse=True)

            # Format notes for display
            if active_notes:
                column = [format_note_3char(note) for note in active_notes]
            else:
                column = ['---']  # Silence

            sheet_music_columns.append(column)

            time.sleep(frame_duration)

            frame_number += 1

    cap.release()

    # Write sheet music to file
    print("Generating sheet music...")
    with open(sheet_music_file, 'w') as sheet_f:
        # Find maximum number of simultaneous notes across all frames
        max_notes = max(len(col) for col in sheet_music_columns) if sheet_music_columns else 1

        # Build sheet music lines (each line is a row)
        for row_idx in range(max_notes):
            row_parts = []
            prev_note = None  # Track previous note to detect repeats

            for col_idx, col in enumerate(sheet_music_columns):
                if row_idx < len(col):
                    current_note = col[row_idx]

                    # Check if this note is the same as previous
                    if current_note != '---' and current_note == prev_note:
                        row_parts.append('---')  # Replace repeated note with silence
                    else:
                        row_parts.append(current_note)
                        prev_note = current_note  # Update previous note
                else:
                    row_parts.append('---')  # Fill empty spaces
                    prev_note = '---'

            # Join with spaces and write line
            sheet_line = ' '.join(row_parts) + '\n'
            sheet_f.write(sheet_line)

    print(f"\nProcessing complete. Total frames: {frame_number}")
    if failed_frames > 0:
        print(f"Warning: {failed_frames} corrupted frame(s) were skipped")
    print(f"Results saved to: {output_file}")
    print(f"Piano CSV saved to: {piano_csv}")
    print(f"Sheet music saved to: {sheet_music_file}")

    if save_previews:
        print(f"Preview frames saved to: {preview_dir}/")
        print(f"Total preview frames: {(frame_number // 6)}")

def cleanup_previous_runs():
    """Clean up files from previous runs (but keep downloaded videos)"""
    # Remove preview frames directory
    if os.path.exists('preview_frames'):
        os.system('rm -rf preview_frames')
        print("Cleaned up previous preview frames")

    # Remove output files
    if os.path.exists('output.txt'):
        os.system('rm -f output.txt')
        print("Cleaned up previous output.txt")

    if os.path.exists('piano.csv'):
        os.system('rm -f piano.csv')
        print("Cleaned up previous piano.csv")

    if os.path.exists('sheet_music.txt'):
        os.system('rm -f sheet_music.txt')
        print("Cleaned up previous sheet_music.txt")

    # Note: We intentionally keep downloaded_videos directory to avoid re-downloading

def main():
    """Main program entry point"""
    print("Light to Sheet - Video Brightness Analysis Tool")
    print("=" * 50)

    # Clean up any previous run data
    cleanup_previous_runs()
    print()

    # Ask for input type
    print("Choose input source:")
    print("1. YouTube URL")
    print("2. Local video file")
    choice = input("Enter choice (1 or 2): ").strip()

    video_source = None
    if choice == '1':
        url = input("Enter YouTube video URL: ").strip()
        if not url:
            print("Error: No URL provided")
            return
        video_source = download_youtube_video(url)
    elif choice == '2':
        file_path = input("Enter video file path (relative or absolute): ").strip()
        if not file_path:
            print("Error: No file path provided")
            return
        # Handle relative paths
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return
        video_source = file_path
        print(f"Using local file: {video_source}")
    else:
        print("Invalid choice")
        return

    # Ask if user wants to save preview frames
    save_previews = input("Save preview frames? (y/n, default: y): ").strip().lower()
    save_previews = save_previews != 'n'  # Default to yes unless explicitly no

    try:
        temp_processed = os.path.join(tempfile.gettempdir(), 'video_processed.mp4')
        preprocess_video(video_source, temp_processed)

        process_video(temp_processed, 'output.txt', save_previews)

        # Only remove temp processed file, not the source
        if os.path.exists(temp_processed):
            os.remove(temp_processed)

    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    main()
