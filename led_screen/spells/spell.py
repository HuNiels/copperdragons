#!/usr/bin/env python
import os
import sys
import time

from pathlib import Path
import json

from samplebase import SampleBase

# One-shot spell: play all frames or stop after this many seconds (whichever is shorter), then clear the panel.
SPELL_MAX_SECONDS = float(os.environ.get("SPELL_MAX_SECONDS", "10"))

#Define what spell to 'cast', lowercase
valid_spells = ["fireball", "void"]
selected_spell = ""

arguments = sys.argv

for argument in arguments:
    if argument in valid_spells:
        index = arguments.index(argument)
        selected_spell = arguments.pop(index)
        break

sys.argv = arguments

if not selected_spell:
    print(f"No spell selected, please select one of the following spells: {valid_spells}")
    sys.exit()

FRAME_DATA_FOLDER = Path(f"../spell-data/{selected_spell}")
FRAME_TIME = 0.1

GRID = "grid"
PALETTE = "palette"

FRAMES = max(
    int(f.stem.split('_')[-1])
    for f in FRAME_DATA_FOLDER.glob(f"{selected_spell}-frame_*.json")
)

class Spell(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Spell, self).__init__(*args, **kwargs)

    def run(self):
        deadline = time.monotonic() + SPELL_MAX_SECONDS
        colours_path = f"{FRAME_DATA_FOLDER}/{selected_spell}-colours.json"
        with open(colours_path, "r") as f:
            spell_matrix_colours = json.load(f)
        try:
            for frame in range(FRAMES):
                if time.monotonic() >= deadline:
                    break
                with open(f"{FRAME_DATA_FOLDER}/{selected_spell}-frame_{frame}.json", "r") as f:
                    spell_matrix = json.load(f)

                offset_canvas = self.matrix.CreateFrameCanvas()

                for x in range(0, len(spell_matrix[GRID][0])):
                    for y in range(0, len(spell_matrix[GRID])):
                        colour_index = spell_matrix[GRID][y][x]
                        colour = spell_matrix_colours[PALETTE][colour_index]
                        r = colour["r"]
                        g = colour["g"]
                        b = colour["b"]
                        offset_canvas.SetPixel(x, y, r, g, b)

                self.matrix.SwapOnVSync(offset_canvas)

                time.sleep(FRAME_TIME)
        finally:
            self.matrix.Clear()
    
# Main function
if __name__ == "__main__":
    spell = Spell()
    if (not spell.process()):
        spell.print_help()
