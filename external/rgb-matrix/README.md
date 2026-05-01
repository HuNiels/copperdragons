# rgb-matrix (vendored, trimmed)

This is a vendored, trimmed copy of [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix),
the C++ library + Python bindings used by Copperdragons to drive the LED panel
from `led_screen/spells/spell.py`. It was originally imported into the repo in
commit `7d6edda` ("Created package from external dependencies, general clean up");
the exact upstream commit / tag is not recorded.

See the upstream project for full documentation, hardware wiring, panel
configuration, and the original demos.

## What this copy keeps

- `lib/` — the C++ library that builds `librgbmatrix.a` / `librgbmatrix.so.1`.
- `include/` — public headers consumed by `lib/` and the bindings.
- `bindings/python/` — the `core` extension (`RGBMatrix`, `RGBMatrixOptions`,
  `FrameCanvas`) plus the package metadata. `samplebase.py` lives in
  `led_screen/spells/` instead.
- `fonts/7x13.bdf` — bundled BDF font referenced by `led_screen/spells/runtext.py`.
- `COPYING` — GPL-2.0-or-later license text.

## What this copy removes (vs upstream)

- `adapter/` (KiCad PCB projects), `bindings/c#/` (alternate language binding),
  `examples-api-use/` (C++ demos), `utils/` (image / text / video viewers),
  `.github/` (upstream CI).
- `bindings/python/samples/` (upstream demo scripts and `samplebase.py`).
- The Python `graphics` extension (`graphics_ext`, `rgbmatrix/graphics.pyx`,
  `graphics.pxd`). The C++ `graphics.cc` / `bdf-font.cc` are still linked into
  `librgbmatrix`; only the Python wrapper is gone.
- Generated metadata (`*.egg-info/`, `build/`, `__pycache__/`).

## How to build

From the repo root, in the project venv:

```bash
make -C external/rgb-matrix build-python
pip install -e external/rgb-matrix/bindings/python
```

`scripts/setup.sh` runs the same steps automatically. After building,
`led_screen/spells/spell.py` will load the `core` extension via
`from rgbmatrix import RGBMatrix, RGBMatrixOptions`.

## License

Original library is (c) Henner Zeller, licensed under
[GNU General Public License Version 2.0 (or any later version)](http://www.gnu.org/licenses/gpl-2.0.txt).
The unmodified license text is preserved verbatim in [`COPYING`](./COPYING).
