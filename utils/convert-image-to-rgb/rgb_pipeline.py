import argparse
from pathlib import Path
from PIL import Image
import json
import re

from rgb_extract import ImageRGBExtractor


class Palette:
    def __init__(self):
        self.rgb_to_index = {}
        self.index_to_rgb = []

    @staticmethod
    def _distance(c1, c2):
        return (
                (c1[0] - c2[0]) ** 2 +
                (c1[1] - c2[1]) ** 2 +
                (c1[2] - c2[2]) ** 2
        ) ** 0.5

    def get_index(self, rgb, threshold=12):
        rgb = tuple(int(x) for x in rgb)

        # 1. Try to match existing colors
        best_idx = None
        best_dist = float("inf")

        for i, existing in enumerate(self.index_to_rgb):
            existing_rgb = (existing["r"], existing["g"], existing["b"])
            dist = self._distance(rgb, existing_rgb)

            if dist < best_dist:
                best_dist = dist
                best_idx = i

        # 2. If close enough → reuse existing color
        if best_dist <= threshold:
            return best_idx

        # 3. Otherwise create new color
        idx = len(self.index_to_rgb)
        self.index_to_rgb.append(
            {"r": rgb[0], "g": rgb[1], "b": rgb[2]}
        )
        return idx

    def save(self, path):
        with open(path, "w") as f:
            f.write("{\n")
            f.write('    "palette": [\n')

            for i, color in enumerate(self.index_to_rgb):
                line = (
                    "        {"
                    f'"r":{color["r"]},'
                    f'"g":{color["g"]},'
                    f'"b":{color["b"]}'
                    "}"
                )
                if i < len(self.index_to_rgb) - 1:
                    line += ","
                f.write(line + "\n")

            f.write("    ]\n")
            f.write("}\n")


def reconstruct_image(grid, palette, output_path):
    height = len(grid)
    width = len(grid[0])

    img = Image.new("RGB", (width, height))

    for y, row in enumerate(grid):
        for x, idx in enumerate(row):
            color = palette[idx]
            img.putpixel((x, y), (color["r"], color["g"], color["b"]))

    img.save(output_path)


def run_extractor(image_path, output_path, palette):
    extractor = ImageRGBExtractor(image_path, palette)
    extractor.run(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument(
        "--reconstruct",
        action="store_true",
        help="Enable saving reconstructed images"
    )

    args = parser.parse_args()

    input_dir = Path(args.folder)
    output_dir = Path("image_output") / input_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_extensions = {".jpg", ".jpeg", ".png", ".gif"}

    images = sorted(
        [p for p in input_dir.rglob("*") if p.suffix.lower() in valid_extensions]
    )

    if not images:
        raise FileNotFoundError(f"No images found in {input_dir}")

    palette = Palette()

    frame_data = []

    dataset_name = input_dir.name

    for img in images:
        match = re.search(r"frame_(\d+)", img.stem)
        frame_number = str(int(match.group(1))) if match else img.stem
        out_json = output_dir / f"{dataset_name}-frame_{frame_number}.json"
        run_extractor(img, out_json, palette)
        frame_data.append((img.stem, out_json))

    palette_path = output_dir / f"{dataset_name}-colours.json"
    palette.save(palette_path)

    # 3. Optional reconstruction
    if args.reconstruct:
        palette_list = palette.index_to_rgb

        for stem, json_path in frame_data:
            with open(json_path, "r") as f:
                data = json.load(f)

            grid = data["grid"]

            out_img = output_dir / f"{stem}_reconstructed.png"
            reconstruct_image(grid, palette_list, out_img)

        print("Reconstruction: enabled")
    else:
        print("Reconstruction: skipped (default)")

    print("\nDone!")
    print(f"Input:   {input_dir}")
    print(f"Output:  {output_dir}")
    print(f"Palette: {palette_path}")


if __name__ == "__main__":
    main()