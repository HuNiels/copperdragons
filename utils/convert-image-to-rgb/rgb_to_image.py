import json
import argparse
from PIL import Image

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def json_to_image(json_path, output_path):
    with open(json_path, "r") as f:
        data = json.load(f)

    height = len(data)
    width = len(data[0])

    img = Image.new("RGB", (width, height))

    for y, row in enumerate(data):
        for x, hex_color in enumerate(row):
            rgb = hex_to_rgb(hex_color)
            img.putpixel((x, y), rgb)

    # Save image
    img.save(output_path)
    print(f"Image saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert hex pixel JSON back into an image.")
    parser.add_argument("json_file", help="Path to pixel_colors.json")
    parser.add_argument("--output", default="reconstructed.png", help="Output image file name")

    args = parser.parse_args()

    json_to_image(args.json_file, args.output)