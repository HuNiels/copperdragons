import argparse
import json
from pathlib import Path

from PIL import Image
import numpy as np

class ImageRGBExtractor:
    def __init__(self, image_path):
        self.image_path = Path(image_path)
        self.image = None
        self.pixel_data = []

    def _load_image(self):
        img_pil = Image.open(self.image_path).convert("RGB")

        img_pil = img_pil.resize((32, 32), resample=Image.Resampling.NEAREST)

        self.image = np.array(img_pil)

        print(f"Resized image shape: {self.image.shape}")

    @staticmethod
    def _rgb_to_hex(pixel):
        r, g, b = pixel[:3]

        if isinstance(r, float):
            r, g, b = int(r * 255), int(g * 255), int(b * 255)
        else:
            r, g, b = int(r), int(g), int(b)

        return f"#{r:02x}{g:02x}{b:02x}"

    def _extract_hex(self):
        if self.image is None:
            raise ValueError("Image not loaded. Call _load_image() first.")

        for row in self.image:
            row_data = []
            for pixel in row:
                row_data.append(self._rgb_to_hex(pixel))
            self.pixel_data.append(row_data)

    def _save_to_json(self):
        output_path = self.image_path.parent / "pixel_colors.json"

        with open(output_path, "w") as f:
            f.write("[\n")

            for i, row in enumerate(self.pixel_data):
                row_str = json.dumps(row)

                if i < len(self.pixel_data) - 1:
                    f.write(f"  {row_str},\n")
                else:
                    f.write(f"  {row_str}\n")

            f.write("]\n")

        print(f"Hex color data saved to: {output_path}")

    def run(self):
        self._load_image()
        self._extract_hex()
        self._save_to_json()
        print(f"Extracted {len(self.pixel_data)} rows of pixels.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract HEX color values from an image.")
    parser.add_argument("image_path", help="Path to the image file (e.g. cat.jpeg)")
    args = parser.parse_args()

    extractor = ImageRGBExtractor(args.image_path)
    extractor.run()