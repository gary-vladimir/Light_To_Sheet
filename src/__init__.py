"""
Light to Sheet - Piano Note Detection from Video

A modular application that analyzes Synthesia-style piano videos to detect
key presses by extracting brightness patterns across 88 vertical slices.

Public API (imported lazily to avoid heavy dependency loading at import time)::

    from src.video_downloader import download_youtube_video
    from src.video_processor import preprocess_video, process_video
"""

__version__ = "1.0.0"
