This app is working as intended, but there is a critical logical bug that does not allow the app to work as well as it could be.

The mistake lies in the way we visually detect the keys being pressed. Currently in the config.py file we have a list of vertical slices that represent the width of each key>

```py
# Piano key slice widths (88 keys total)
# These represent the pixel widths for each vertical slice.
# Pattern: white keys are wider (28-33px), black keys are narrower (15-21px)
_OCTAVE_PATTERN: list[int] = [28, 15, 21, 15, 28, 28, 15, 20, 15, 21, 15, 28]
VERTICAL_SLICES: list[int] = [29, 15, 28] + (_OCTAVE_PATTERN * 7) + [33]

```

This introduced a big problem that i overlooked. the problem is that this system assumes the "light beams" in the synthesia style video don't overlap with other notes. This idea actually works with only the white keys, because white keys don't overlap with their neighbors keys. But this idea totally fails for black keys, because a black key is BETWEEN two white keys, they are not separated.
Ideal scenario>
"
WHITE KEY | BLACK KEY | WHITE KEY | BLACK KEY |
"

actual scenario>
"
    |BLACK KEY|      |BLACK KEY|
WHITE KEY  |  WHITE KEY  | WHITE KEY  |
"

This is a bit hard to visualize in an ascii diagram, but the point is that the black keys are not separated from the white keys.

I will give you one practical example scenario of the issue:

Imagine there is a light beam falling for C#4 (which is a black key).

Right now, our system detects C#4 as an actively pressed key. But, that same light beam is "over flowing" or "spilling" onto the neighboring white keys, which are C4 and D4.

So our system detects C#4, C4, and D4 as actively pressed keys.

But in reality, only C#4 is an actively pressed key. This issue is especially prominent with black keys. But it also happens with white keys, e.g:

Imagine there is a light beam falling for D4 (which is a white key).

Right now, our system correctly detects D4 as an actively pressed key. But, that same light beam is "over flowing" or "spilling" onto the neighboring black keys, which are D#4 and C#4.

Hopefully the issue is more clear. Given the issue, we have to change the array of vertical slices aproach to something completely different.

I propose the following solution:

Separate the white keys and black keys into two different arrays.

We have a total of 52 white keys and 36 black keys.

We process the white keys in the same way we do now, but we only process the black keys in a different way.

for the white keys simply devide the entire width of the video into 52 equal slices, and check the brightness of each slice.

For the black keys, we need to process them in a different way.

I propose the following approach for black keys only:

1. We locate the CENTER of the black key. This can be easy to find, the center of the black key is always exactly located between two white keys. (when one white key ends, and the other one starts, there is the center of a black key).

Once we locate the center of all the black keys, (we must not forget that in between B and C and between E and F there are no black keys!)

But once we get all the centers of the black keys, we can then create a "box" around the center of each black key. This box will be the area where we check for brightness. This box should be smaller than the width of a white key slice. (white keys are wider 30-40px, black keys are narrower 15-22px aprox)

Here is the new critical detail:

Once we check the brightness of the black key box, IF it's bright enough to be considered a pressed key, we then create a new box, however... this new box is not centered on the black key. this new box starts at the center of the black key and extends to the right, covering the right half of the black key and the left half of the white key to its right. We then repeat the same process, but this time we create a new box that starts at the center of the black key and extends to the left, covering the left half of the black key and the right half of the white key to its left.

IF ANY of these two boxes are bright enough to be considered a pressed key, we then REMOVE the black key as pressed.

IF ANY of these two boxes are bright enough, it means that the current black key "been pressed" is not actually pressed, but it is just a "spill over" from the neighboring white keys.

> careful! the brightness threshold for these 2 additional boxes should consider the fact that in theory half of the box is black key, and the other half is white key. So this means that if the black key is pressed, and the white key is not pressed, the brightness in total should be split in half. and if both the black key and the white key are pressed, the brightness in total should be much greater. I recommend the following> if the brightness of any of these 2 additional boxes is greater than 90% of the original brightness threshold, then we remove the black key as pressed.

This is the new logic i propose, this is the initial solution idea. However.... i am just proposing a recomendation, i want you to understand my idea, and based on it, create the final, new, and improved solution.

Be very creative, and think outside the box. The goal is to create a RELIABLE solution.

I strongly belive that keeping the solution simple is the key to success.

This problem might be solved with simple conditionals and logic!

I am confident that there is no need to overcomplicate this, and that you can come up with a solution that is both simple and effective.
