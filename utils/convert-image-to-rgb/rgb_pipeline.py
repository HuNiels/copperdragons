import argparse
import subprocess
from pathlib import Path
import sys

IMAGE_SOURCE_DIR = Path("image_source")
IMAGE_OUTPUT_DIR = Path("image_output")


def run_extractor(image_path):
    subprocess.run(
        [sys.executable, "rgb_extract.py", str(image_path)],
        check=True
    )


def run_reconstructor(json_path, output_path):
    subprocess.run(
        [
            sys.executable,
            "rgb_to_image.py",
            str(json_path),
            "--output",
            str(output_path)
        ],
        check=True
    )


def main():
    parser = argparse.ArgumentParser(description="Image pipeline")

    parser.add_argument("image", help="Input image filename (e.g. cat.jpeg)")

    args = parser.parse_args()

    IMAGE_OUTPUT_DIR.mkdir(exist_ok=True)

    source_image = IMAGE_SOURCE_DIR / args.image

    if not source_image.exists():
        raise FileNotFoundError(f"Image not found: {source_image}")

    stem = source_image.stem  # "cat"

    # 👇 JSON name tied to input
    json_path = IMAGE_OUTPUT_DIR / f"{stem}_pixel_colors.json"

    # 👇 FINAL output name you requested
    output_image = IMAGE_OUTPUT_DIR / f"{stem}_small.png"

    # Step 1: extract
    run_extractor(source_image)

    # Move JSON into output folder with correct name
    generated_json = source_image.parent / "pixel_colors.json"
    generated_json.rename(json_path)

    # Step 2: reconstruct
    run_reconstructor(json_path, output_image)

    print("\nPipeline complete!")
    print(f"Input: {source_image}")
    print(f"JSON: {json_path}")
    print(f"Output: {output_image}")


if __name__ == "__main__":
    main()