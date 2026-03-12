#!/usr/bin/env python3
"""
Light to Sheet - Piano Note Detection from Video

Analyzes Synthesia-style piano videos to detect key presses by extracting
brightness patterns across 88 vertical slices (one per piano key, A0 to C8).

Run as: python main.py
"""

from __future__ import annotations

import os
import tempfile

import inquirer

from src.utils import cleanup_previous_runs, get_downloaded_videos
from src.video_downloader import download_youtube_video
from src.video_processor import preprocess_video, process_video


def get_video_source() -> str | None:
    """Prompt user for video source (YouTube URL or local file).

    Returns:
        Path to video file, or None if selection failed.
    """
    print("Choose input source:")
    print("1. YouTube URL")
    print("2. Local video file")
    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        return _get_youtube_video()
    elif choice == "2":
        return _get_local_video()
    else:
        print("Invalid choice")
        return None


def _get_youtube_video() -> str | None:
    """Download a video from YouTube.

    Returns:
        Path to downloaded video, or None on failure.
    """
    url = input("Enter YouTube video URL: ").strip()
    if not url:
        print("Error: No URL provided")
        return None

    custom_title = input(
        "Enter a custom filename for the video (or press Enter to use video ID): "
    ).strip() or None

    return download_youtube_video(url, custom_title)


def _get_local_video() -> str | None:
    """Select a local video file via interactive menu or manual path.

    Returns:
        Path to selected video, or None on failure.
    """
    available_videos = get_downloaded_videos()

    if not available_videos:
        print("No videos found in downloaded_videos/ folder")
        return _get_manual_file_path()

    print(f"\nFound {len(available_videos)} video(s) in downloaded_videos/")
    choices = available_videos + ["Browse for another file..."]

    questions = [
        inquirer.List(
            "video",
            message="Select a video file (use arrow keys)",
            choices=choices,
            carousel=True,
        )
    ]

    try:
        answers = inquirer.prompt(questions)
        if not answers:
            print("Selection cancelled")
            return None

        selected = answers["video"]
        if selected == "Browse for another file...":
            return _get_manual_file_path()

        video_source = os.path.join("downloaded_videos", selected)
        print(f"Selected: {video_source}")
        return video_source

    except KeyboardInterrupt:
        print("\nSelection cancelled")
        return None


def _get_manual_file_path() -> str | None:
    """Get file path from manual user input.

    Returns:
        Validated absolute file path, or None if invalid.
    """
    file_path = input("Enter video file path (relative or absolute): ").strip()
    if not file_path:
        print("Error: No file path provided")
        return None

    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return None

    print(f"Using local file: {file_path}")
    return file_path


def main() -> None:
    """Main program entry point."""
    print("Light to Sheet - Video Brightness Analysis Tool")
    print("=" * 50)

    cleanup_previous_runs()
    print()

    video_source = get_video_source()
    if not video_source:
        return

    save_input = input("Save preview frames? (y/n, default: y): ").strip().lower()
    save_previews = save_input != "n"

    try:
        temp_processed = os.path.join(tempfile.gettempdir(), "video_processed.mp4")
        preprocess_video(video_source, temp_processed)
        process_video(temp_processed, output_dir=".", save_previews=save_previews, realtime=True)
    except Exception as e:
        print(f"Error: {e}")
        return
    finally:
        temp_path = os.path.join(tempfile.gettempdir(), "video_processed.mp4")
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    main()
