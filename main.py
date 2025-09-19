# CODE COMING UP
"""
This program should be run as python main.py
And the workflow should be as follows>
1. the user is prompeted to enter a link to a youtube video
2. the script shall download the video and resize it to 1920x1080
3. the script shall make the video 24fps while mantaining the original speed (video duration should be the same)
4. the script shall iterate each frame from output 24fps video.
5. each frame shall be converted to gray scale
6. the script shall define a state array of size 88
7. for each frame, the script shall devide the frame into 88 vertical slices
8. for each slice size (1920/88 = 21.81818181818182 pixels) define a zone of interest. the zone of interest should be 1px tall and 21.81818181818182px wide and aligned at the top of the frame
9. for each zone of interest, the script shall calculate the average brightness and store it in the state array at the index of the slice
10. after processing all 88 slices, the script shall print the state array
11. the script shall wait for 1/24 seconds before processing the next frame
12. the script shall repeat steps 7-11 until all frames are processed
13. the script shall then exit

all state arrays shall be printed to the console and additionally saved to a text file named output.txt
the output.txt file shall contain one state array per line with a timestamp of when the frame was processed e.g "[23, 45, 67, 89, ...] 00:00:01.234567"
"""

