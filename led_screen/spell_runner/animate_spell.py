#!/usr/bin/env python
import json
import sys
import time
from pathlib import Path
from typing import TypedDict

from samplebase import SampleBase

SINGLE_SPELL_SECONDS = 5
PLAYLIST_SPELL_SECONDS = 5
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


def pop_positional_arg() -> str:
    """Remove and return the first non-flag argument from sys.argv (if any)."""
    for i, arg in enumerate(sys.argv[1:], 1):
        if not arg.startswith("-"):
            return sys.argv.pop(i)
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
    def __init__(self, spell_names: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spell_names = spell_names
        self.seconds_per_spell = SINGLE_SPELL_SECONDS if len(spell_names) == 1 else PLAYLIST_SPELL_SECONDS

    def run(self) -> None:
        canvas = self.matrix.CreateFrameCanvas()
        for spell_name in self.spell_names:
            spell_dir = SPELL_DATA_ROOT / spell_name
            palette = load_palette(spell_dir, spell_name)
            frames = load_frames(spell_dir, spell_name)
            print(f"Playing: {spell_name}")
            self._animate(canvas, frames, palette, self.seconds_per_spell)

    def _animate(
        self,
        canvas,
        frames: list[Grid],
        palette: list[Colour],
        max_seconds: int,
    ) -> None:
        deadline = time.monotonic() + max_seconds

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
spell_arg = pop_positional_arg()

if spell_arg:
    if spell_arg not in valid_spells:
        print(f"Unknown spell '{spell_arg}'. Choose one of: {valid_spells}")
        sys.exit(1)
    spell_names = [spell_arg]
else:
    if not valid_spells:
        print("No spells found in spell_data directory.")
        sys.exit(1)
    print(f"No spell specified — playing all {len(valid_spells)} spells ({PLAYLIST_SPELL_SECONDS}s each).")
    spell_names = valid_spells

if __name__ == "__main__":
    spell = AnimateSpell(spell_names)
    if not spell.process():
        spell.print_help()  # type: ignore