# Light to Sheet - Video Brightness Analysis Tool
"""
This program analyzes YouTube videos to extract brightness patterns across 88 vertical slices.
Run as: python main.py

Workflow:
1. User is prompted to enter a YouTube video link
2. Video is downloaded and resized to 1848x1080 (stretch to fit, no aspect ratio preservation)
   - Width is 1848px instead of 1920px to ensure integer slice widths (21px each)
3. Video is converted to 24fps while maintaining original speed/duration
4. Each frame is processed sequentially:
   a. Convert frame to grayscale
   b. Divide frame into 88 vertical slices (each 21px wide x 1080px tall)
   c. For each slice, analyze a 1px tall x 21px wide zone at the top of the frame
   d. Calculate average brightness (simple mean of pixel values 0-255)
   e. Store brightness as percentage (0-100) in state array
5. Output each state array to console and append to output.txt
6. Wait 1/24 seconds between frames (for real-time processing simulation)
7. Continue until all frames processed

Output Format:
- Console: Print each state array as processed
- output.txt: One state array per line with video timestamp
  Format: "[23.5, 45.2, 67.8, ...] HH:MM:SS.ffffff"
  - Timestamps represent frame presentation time in the video
  - Each line is 1/24 seconds apart (41.67ms intervals)
  - Brightness values are percentages (0.0 to 100.0)

Technical Notes:
- Use simple/lightweight YouTube download library
- Brightness = mean(grayscale_pixel_values) / 255 * 100
- Processing delay enables future real-time state queries
- Timestamps allow correlation between state arrays and video playback time
"""

helper = [28,15,21,15,28,28,15,20,15,21,15,28]
vertical_slices = [29,15,28] + (helper*7) + [33]
tags = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
slices_tags = ["A", "A#", "B"] + (tags*7) + "C"

import cv2
import numpy as np
import yt_dlp
import os
import time
import tempfile
from datetime import timedelta

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
    """Resize video to 1848x1080 and convert to 24fps"""
    print("Preprocessing video...")

    cap = cv2.VideoCapture(input_path)
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 24.0, (1848, 1080))

    frame_interval = original_fps / 24.0
    frame_counter = 0.0
    processed_frames = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_counter))
        ret, frame = cap.read()
        if not ret or frame_counter >= total_frames:
            break

        resized = cv2.resize(frame, (1848, 1080), interpolation=cv2.INTER_LINEAR)
        out.write(resized)

        frame_counter += frame_interval
        processed_frames += 1

    cap.release()
    out.release()

    print(f"Video preprocessed: {processed_frames} frames at 24fps")
    return output_path

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
    fps = 24.0
    frame_duration = 1.0 / fps
    frame_number = 0

    with open(output_file, 'w') as f:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

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

            time.sleep(frame_duration)

            frame_number += 1

    cap.release()

    print(f"\nProcessing complete. Total frames: {frame_number}")
    print(f"Results saved to: {output_file}")

    if save_previews:
        print(f"Preview frames saved to: {preview_dir}/")
        print(f"Total preview frames: {(frame_number // 6)}")

def cleanup_previous_runs():
    """Clean up files from previous runs (but keep downloaded videos)"""
    # Remove preview frames directory
    if os.path.exists('preview_frames'):
        os.system('rm -rf preview_frames')
        print("Cleaned up previous preview frames")

    # Remove output file
    if os.path.exists('output.txt'):
        os.system('rm -f output.txt')
        print("Cleaned up previous output.txt")

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
