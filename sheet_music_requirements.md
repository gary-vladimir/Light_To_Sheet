The script shall create an additional sheet music output file like the one described below>

the file represents a timeline, the file should expand from left to right. not up to down. 

the file is essentially a very simple ascii sheet music representation.

e.g the final output should ressamble this>

```
C5  D4  F4  B4  --- D4
D3  --- C4  G#4 --- B3
--- --- --- D4  --- 
```

notice how each column represents a "frame", the first column would be 00:00:00. and the next column would be 00:00:041667.

Each column should be order in acending order, this means that the lowest notes shall go at the bottom in that same column. and the higher pitch notes should go at the top in that same column. Be careful with the ordering feature, we are NOT ordering alphabetically, this is music, remember the rules for a higher pitch note. e.g C#4 is greater than C4. music rules apply.

the spaces without any notes been played (silences) shall also be represented by a "---" string for example. the file should be clearly visibly appealing and easy to understand, everything should go perfectly aligned. to achieve this successfully i recommend that all notes be represented by exacly three characters, this is because of the longest note representation scenario "G#3" example. 