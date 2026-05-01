#!/usr/bin/env python
import os
import sys
import time

from pathlib import Path
import json

from samplebase import SampleBase

# Spell: play all frames SPELL_LOOPS times (default 5), or stop after SPELL_MAX_SECONDS (whichever is shorter), then clear.
SPELL_MAX_SECONDS = float(os.environ.get("SPELL_MAX_SECONDS", "10"))
try:
    SPELL_LOOPS = max(1, int(os.environ.get("SPELL_LOOPS", "5")))
except ValueError:
    SPELL_LOOPS = 5

SPELL_DATA_ROOT = Path(__file__).resolve().parent.parent / "spell-data"
if SPELL_DATA_ROOT.is_dir():
    valid_spells = sorted(
        d.name
        for d in SPELL_DATA_ROOT.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
else:
    valid_spells = []
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

FRAME_DATA_FOLDER = SPELL_DATA_ROOT / selected_spell
FRAME_TIME = 0.1

GRID = "grid"
PALETTE = "palette"

# Frame files are named {spell}-frame_0.json .. {spell}-frame_N.json (inclusive).
MAX_FRAME_INDEX = max(
    int(f.stem.split("_")[-1])
    for f in FRAME_DATA_FOLDER.glob(f"{selected_spell}-frame_*.json")
)
FRAME_COUNT = MAX_FRAME_INDEX + 1

class Spell(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Spell, self).__init__(*args, **kwargs)

    def run(self):
        deadline = time.monotonic() + SPELL_MAX_SECONDS
        colours_path = f"{FRAME_DATA_FOLDER}/{selected_spell}-colours.json"
        with open(colours_path, "r") as f:
            spell_matrix_colours = json.load(f)
        # One offscreen buffer: CreateFrameCanvas once, then reuse the canvas
        # returned by SwapOnVSync (see hzeller rgb-matrix README). Calling
        # CreateFrameCanvas inside the frame loop breaks double-buffering.
        offset_canvas = self.matrix.CreateFrameCanvas()
        try:
            for _loop in range(SPELL_LOOPS):
                for frame in range(FRAME_COUNT):
                    if time.monotonic() >= deadline:
                        break
                    with open(f"{FRAME_DATA_FOLDER}/{selected_spell}-frame_{frame}.json", "r") as f:
                        spell_matrix = json.load(f)

                    offset_canvas.Clear()
                    for x in range(0, len(spell_matrix[GRID][0])):
                        for y in range(0, len(spell_matrix[GRID])):
                            colour_index = spell_matrix[GRID][y][x]
                            colour = spell_matrix_colours[PALETTE][colour_index]
                            r = colour["r"]
                            g = colour["g"]
                            b = colour["b"]
                            offset_canvas.SetPixel(x, y, r, g, b)

                    offset_canvas = self.matrix.SwapOnVSync(offset_canvas)

                    time.sleep(FRAME_TIME)
                else:
                    continue
                break
        finally:
            offset_canvas.Clear()
            self.matrix.SwapOnVSync(offset_canvas)
    
# Main function
if __name__ == "__main__":
    spell = Spell()
    if (not spell.process()):
        spell.print_help()
