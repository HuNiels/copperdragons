#!/usr/bin/env python
import json
import sys
import time
from pathlib import Path
from typing import TypedDict

from samplebase import SampleBase

MAX_SECONDS = 120
FRAME_TIME = 0.1
SPELL_DATA_ROOT = Path(__file__).resolve().parent.parent / "spell_data"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class Colour(TypedDict):
    r: int
    g: int
    b: int

Grid = list[list[int]]


# ---------------------------------------------------------------------------
# Spell selection
# ---------------------------------------------------------------------------

def find_valid_spells(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        directory.name for directory in root.iterdir()
        if directory.is_dir() and not directory.name.startswith(".")
    )


def pop_spell_from_argv(valid_spells: list[str]) -> str:
    """Remove and return the first recognised spell name from sys.argv."""
    for i, arg in enumerate(sys.argv):
        if arg in valid_spells:
            sys.argv.pop(i)
            return arg
    return ""


# ---------------------------------------------------------------------------
# Frame data loading
# ---------------------------------------------------------------------------

def load_frames(spell_dir: Path, spell_name: str) -> list[Grid]:
    """Load every frame grid in order and return them as a list."""
    frame_files = sorted(
        spell_dir.glob(f"{spell_name}-frame_*.json"),
        key=lambda f: int(f.stem.split("_")[-1]),
    )
    if not frame_files:
        raise FileNotFoundError(f"No frame files found in {spell_dir}")

    return [json.loads(f.read_text())["grid"] for f in frame_files]


def load_palette(spell_dir: Path, spell_name: str) -> list[Colour]:
    colours_path = spell_dir / f"{spell_name}-colours.json"
    return json.loads(colours_path.read_text())["palette"]


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class AnimateSpell(SampleBase):
    def __init__(self, spell_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spell_name = spell_name

    def run(self) -> None:
        spell_dir = SPELL_DATA_ROOT / self.spell_name
        palette = load_palette(spell_dir, self.spell_name)
        frames = load_frames(spell_dir, self.spell_name)
        self._animate(frames, palette)

    def _animate(self, frames: list[Grid], palette: list[Colour]) -> None:
        deadline = time.monotonic() + MAX_SECONDS
        canvas = self.matrix.CreateFrameCanvas()

        try:
            while time.monotonic() < deadline:
                for grid in frames:
                    if time.monotonic() >= deadline:
                        return
                    self._draw_frame(canvas, grid, palette)
                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(FRAME_TIME)
        finally:
            canvas.Clear()
            self.matrix.SwapOnVSync(canvas)

    @staticmethod
    def _draw_frame(canvas, grid: Grid, palette: list[Colour]) -> None:
        canvas.Clear()
        for y, row in enumerate(grid):
            for x, colour_index in enumerate(row):
                c = palette[colour_index]
                canvas.SetPixel(x, y, c["r"], c["g"], c["b"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

valid_spells = find_valid_spells(SPELL_DATA_ROOT)
spell_name = pop_spell_from_argv(valid_spells)

if not spell_name:
    print(f"No valid spell selected. Choose one of: {valid_spells}")
    sys.exit(1)

if __name__ == "__main__":
    spell = AnimateSpell(spell_name)
    if not spell.process():
        spell.print_help() # type: ignore
