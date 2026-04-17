#!/usr/bin/env python
from attr import dataclass
import time

from samplebase import SampleBase
from dataclasses import dataclass

IMAGE_WIDTH = 32
IMAGE_HEIGHT = 32

@dataclass
class Colours:
    red: int = 0xFF0000
    green: int = 0x00FF00
    blue: int = 0x0000FF
    white: int = 0xFFFFFF
    black: int = 0x000000
    logo_1: int = 0xDC7742  #Copper
    logo_2: int = 0x567F7F  #Teal
    background_1: int = 0x1A282C #Dark Blue
    background_2: int = 0x372118 #Brown

class ImageBase:
    image_matrix: list[list] = [[0x00 for x in range(IMAGE_WIDTH)] for y in range(IMAGE_HEIGHT)]
    image_colours = Colours()

class LedPrototype(SampleBase):
    def __init__(self, *args, **kwargs):
        super(LedPrototype, self).__init__(*args, **kwargs)

    def run(self):
        offset_canvas = self.matrix.CreateFrameCanvas()
        imagebase = ImageBase()

        zigzag = True

        while True:
            for x in range(0, IMAGE_WIDTH):
                for y in range(0, IMAGE_HEIGHT):
                    current_time_millis = int(round(time.time() * 1000))

                    if ( ((x % 4 == 0 or x % 4 == 1) and y % 4 == 0 ) or ((x % 4 == 1 or x % 4 == 2) and y % 4 == 1 ) or ((x % 4 == 2 or x % 4 == 3) and y % 4 == 2 ) or ((x % 4 == 1 or x % 4 == 2) and y % 4 == 3 )):
                        if (current_time_millis % 926 < 463):
                            imagebase.image_matrix[x][y] = imagebase.image_colours.logo_1
                        else:
                            imagebase.image_matrix[x][y] = imagebase.image_colours.background_1
                    else:
                        if (current_time_millis % 926 < 463):
                            imagebase.image_matrix[x][y] = imagebase.image_colours.background_1
                        else:
                            imagebase.image_matrix[x][y] = imagebase.image_colours.logo_1
                    r, g, b = LedPrototype._hex_to_rgb(self, imagebase.image_matrix[x][y])
                    offset_canvas.SetPixel(x, y, r, g, b)

            offset_canvas = self.matrix.SwapOnVSync(offset_canvas)

    def _hex_to_rgb(self, hex_colour):
        r = (hex_colour >> 16) & 0xFF
        g = (hex_colour >> 8) & 0xFF
        b = hex_colour & 0xFF
        return r, g, b
    
# Main function
if __name__ == "__main__":
    led_prototype = LedPrototype()
    if (not led_prototype.process()):
        led_prototype.print_help()
