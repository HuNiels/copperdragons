#!/usr/bin/env python
import sys

import argparse
parser = argparse.ArgumentParser(description="Spell selection")
parser.add_argument("first_argument", help="The first argument for your script.")
args, unknown_args = parser.parse_known_args()
print(f"Spell selection: {args.first_argument}")
sys.argv = unknown_args  # Set sys.argv to the unknown arguments that the library needs

import os
import time

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))
from samplebase import SampleBase

import json

FRAMES = 8

class Fireball(SampleBase):
    def __init__(self, *args, **kwargs):
        super(Fireball, self).__init__(*args, **kwargs)

    def run(self):
        for frame in range(FRAMES):
            with open(f"../pixel-data/fireball-frame{frame + 1}.json", "r") as f:
                fireball_matrix = json.load(f)

            offset_canvas = self.matrix.CreateFrameCanvas()

            # while True:
            for x in range(0, len(fireball_matrix["grid"][0])):
                for y in range(0, len(fireball_matrix["grid"])):
                    colour_index = fireball_matrix["grid"][y][x]
                    colour = fireball_matrix["palette"][colour_index]
                    r = colour["r"]
                    g = colour["g"]
                    b = colour["b"]
                    offset_canvas.SetPixel(x, y, r, g, b)

            self.matrix.SwapOnVSync(offset_canvas)

            time.sleep(1)
    
# Main function
if __name__ == "__main__":
    fireball = Fireball()
    if (not fireball.process()):
        fireball.print_help()
