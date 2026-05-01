import json
from pathlib import Path
from PIL import Image
import numpy as np

class ImageRGBExtractor:
    def __init__(self, image_path, palette):
        self.image_path = Path(image_path)
        self.palette = palette
        self.image = None
        self.pixel_data = []

    def _load_image(self):
        img = Image.open(self.image_path).convert("RGB")
        img = img.resize((32, 32), Image.Resampling.NEAREST)
        self.image = np.array(img)

    def _extract_indices(self):
        for row in self.image:
            row_data = []
            for pixel in row:
                row_data.append(self.palette.get_index(tuple(pixel)))
            self.pixel_data.append(row_data)

    def save_json(self, output_path):
        with open(output_path, "w") as f:
            f.write("{\n")
            f.write('    "grid": [\n')

            for y, row in enumerate(self.pixel_data):
                row_str = ", ".join(str(v) for v in row)
                line = f"        [{row_str}]"

                if y < len(self.pixel_data) - 1:
                    line += ","

                f.write(line + "\n")

            f.write("    ]\n")
            f.write("}\n")

    def run(self, output_path):
        self._load_image()
        self._extract_indices()
        self.save_json(output_path)
        print(f"Saved: {output_path}")