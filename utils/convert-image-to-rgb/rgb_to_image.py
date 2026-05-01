import json
import argparse
from PIL import Image


def json_to_image(json_path, output_path):
    with open(json_path, "r") as f:
        data = json.load(f)

    palette = data["palette"]
    pixels = data["pixels"]

    height = len(pixels)
    width = len(pixels[0])

    img = Image.new("RGB", (width, height))

    for y, row in enumerate(pixels):
        for x, idx in enumerate(row):
            color = palette[idx]
            rgb = (color["r"], color["g"], color["b"])
            img.putpixel((x, y), rgb)

    img.save(output_path)
    print(f"Image saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert palette-index JSON back into an image.")
    parser.add_argument("json_file", help="Path to JSON file")
    parser.add_argument("--output", default="reconstructed.png", help="Output image file name")

    args = parser.parse_args()

    json_to_image(args.json_file, args.output)