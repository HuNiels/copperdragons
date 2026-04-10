#!/usr/bin/env python
import sys
import os
import time
import re

from pathlib import Path
import json

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

#Define what spell to 'cast', lowercase
valid_spells = ["fireball", "void"]
spell_selected = ""

arguments = sys.argv

for argument in arguments:
    if argument in valid_spells:
        index = arguments.index(argument)
        spell_selected = arguments.pop(index)
        break

sys.argv = arguments

from samplebase import SampleBase

FRAME_FOLDER = Path("../pixel-data")

class Spell(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Spell, self).__init__(*args, **kwargs)

    def run(self):

        if not spell_selected:
            print("No spell selected.")
            sys.exit()

        if spell_selected not in valid_spells:
            print("Selected spell not in spellbook, please try another.")
            sys.exit()

        FRAMES = max(
            int(re.search(r"\d+", f.stem).group())
            for f in FRAME_FOLDER.glob(f"{spell_selected}-frame_*.json")
        )

        while(1):
            for frame in range(FRAMES):
                with open(f"{FRAME_FOLDER}/{spell_selected}-frame_{frame}.json", "r") as f:
                    spell_matrix = json.load(f)

                with open(f"{FRAME_FOLDER}/{spell_selected}-colours.json", "r") as f:
                    spell_matrix_colours = json.load(f)

                offset_canvas = self.matrix.CreateFrameCanvas()

                # while True:
                for x in range(0, len(spell_matrix["grid"][0])):
                    for y in range(0, len(spell_matrix["grid"])):
                        colour_index = spell_matrix["grid"][y][x]
                        colour = spell_matrix_colours["palette"][colour_index]
                        r = colour["r"]
                        g = colour["g"]
                        b = colour["b"]
                        offset_canvas.SetPixel(x, y, r, g, b)

                self.matrix.SwapOnVSync(offset_canvas)

                time.sleep(0.1)
    
# Main function
if __name__ == "__main__":
    spell = Spell()
    if (not spell.process()):
        spell.print_help()
