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

