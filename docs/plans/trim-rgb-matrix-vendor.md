---
name: Trim rgb-matrix vendor
overview: Shrink `external/rgb-matrix` by deleting upstream-only assets (hardware adapters, demos, alternate bindings, CI), fixing the top-level Makefile so builds no longer compile demos, moving `samplebase.py` into `led_screen` so the vendored tree only holds the library + Python bindings, optionally dropping the unused Python `graphics` extension, and validating via a multi-step verification checklist (build, imports, Pi smoke test, escape-room integration). After every milestone, run the `void` spell on the panel as a per-step display gate so the LED stays usable throughout the trim.
todos:
  - id: delete-cruft-dirs
    content: Remove adapter/, bindings/c#/, examples-api-use/, utils/, .github/ under external/rgb-matrix; clean egg-info cruft
    status: pending
  - id: makefile-no-demos
    content: Patch external/rgb-matrix/Makefile to stop building examples-api-use; fix clean targets
    status: pending
  - id: move-samplebase
    content: Add led_screen/spells/samplebase.py; remove bindings/python/samples; update scripts/setup.sh
    status: pending
  - id: optional-graphics-ext
    content: Optionally remove graphics extension from bindings/python/setup.py and delete graphics pyx/pxd/cpp
    status: pending
  - id: vendor-readme
    content: Replace huge README with short vendor note + keep COPYING
    status: pending
  - id: gate-void-after-each-step
    content: After each milestone, run the void spell display gate (rebuild + reinstall first when the milestone touched build/install) per the "Display gate after each milestone" section
    status: pending
  - id: verify-build
    content: "Run full verification checklist: build, pip, imports, spell subprocess, optional API"
    status: pending
---

# Trim `external/rgb-matrix` for Copperdragons

## What actually depends on this tree

- **[scripts/setup.sh](scripts/setup.sh)** runs `make -C external/rgb-matrix build-python`, then `pip install -e external/rgb-matrix/bindings/python`, then `pip install -e external/rgb-matrix/bindings/python/samples`.
- **[led_screen/spells/spell.py](led_screen/spells/spell.py)** imports `SampleBase` from `samplebase` and uses only **`RGBMatrix` / `RGBMatrixOptions`**, **`CreateFrameCanvas()`**, **`SwapOnVSync()`**, and **`SetPixel`** — i.e. the Python **`core`** binding, not `rgbmatrix.graphics`.
- **[escape-room-display/](escape-room-display/)** does not import `rgbmatrix`; it only runs `spell.py` as a subprocess ([spell_runner.py](escape-room-display/spell_runner.py)).

The C library build is defined in [external/rgb-matrix/lib/Makefile](external/rgb-matrix/lib/Makefile) (single `librgbmatrix` from `gpio.o`, `led-matrix.o`, `framebuffer.o`, `graphics.o`, `bdf-font.o`, etc.). **`graphics.cc` / `bdf-font.cc` / `content-streamer.cc` are linked into the shared library** and referenced from `framebuffer.cc`, `led-matrix-c.cc`, etc. **Removing those `.cc` files without a careful fork is high-risk** and saves less disk than deleting demos/adapters. This plan **does not** slim the C object list unless you explicitly want a maintenance-heavy fork later.

## Recommended removals (safe, large impact)

Delete entire directories that are not needed to build `lib/librgbmatrix` or the Python `core` extension:

| Path | Rationale |
|------|-----------|
| [external/rgb-matrix/adapter/](external/rgb-matrix/adapter/) | KiCad projects, zips, passive/active PCB docs — not used at runtime |
| [external/rgb-matrix/bindings/c#/](external/rgb-matrix/bindings/c#/) | Alternate language binding |
| [external/rgb-matrix/examples-api-use/](external/rgb-matrix/examples-api-use/) | C++ demos |
| [external/rgb-matrix/utils/](external/rgb-matrix/utils/) | `led-image-viewer`, `text-scroller`, etc. |
| [external/rgb-matrix/.github/](external/rgb-matrix/.github/) | Upstream CI only |

Also remove stray generated metadata under the vendored tree if present (e.g. multiple `*.egg-info` trees under `bindings/python/` and `bindings/python/samples/`) after fixing installs — they should not be source-of-truth.

## Makefile fix (stops building demos on every `build-python`)

In [external/rgb-matrix/Makefile](external/rgb-matrix/Makefile), the `$(RGB_LIBRARY)` target currently runs `$(MAKE) -C examples-api-use` after building `lib/`. **Remove that dependency** so `make build-python` only builds `lib/` + Python bindings. Update `clean` targets to stop referencing removed dirs.

## Move `samplebase` out of the vendor tree

- Copy [external/rgb-matrix/bindings/python/samples/samplebase.py](external/rgb-matrix/bindings/python/samples/samplebase.py) to **[led_screen/spells/samplebase.py](led_screen/spells/samplebase.py)** (same directory as `spell.py`, so `from samplebase import SampleBase` keeps working with `cwd=led_screen/spells` from [spell_runner.py](escape-room-display/spell_runner.py)).
- Delete `external/rgb-matrix/bindings/python/samples/` (all upstream demo scripts and broken/partial `copperdragons.egg-info`).
- **Update [scripts/setup.sh](scripts/setup.sh):** remove the line `pip install -e external/rgb-matrix/bindings/python/samples`.

## Optional: drop unused Python `graphics` extension

[external/rgb-matrix/bindings/python/setup.py](external/rgb-matrix/bindings/python/setup.py) builds two extensions: `core` and `graphics`. [external/rgb-matrix/bindings/python/rgbmatrix/__init__.py](external/rgb-matrix/bindings/python/rgbmatrix/__init__.py) only imports from `core`. You can remove `graphics_ext` and delete `rgbmatrix/graphics.pyx`, `graphics.cpp` (generated), and `graphics.pxd` **if** nothing in your repo imports `from rgbmatrix import graphics`. (Grep confirms spell path does not.) This slightly speeds installs and shrinks the bindings folder; **`librgbmatrix` still contains C++ graphics/font code** — this only removes the Python wrapper.

## Readability: shorten the vendor README

Replace or heavily trim [external/rgb-matrix/README.md](external/rgb-matrix/README.md) with a short **Copperdragons vendor note**: upstream project URL, original commit/hash if known, what was stripped, and how to build (`make build-python`). Keeps legal notice / [COPYING](external/rgb-matrix/COPYING) intact.

## Display gate after each milestone

After every milestone above, run the same on-panel smoke test using the **`void`** spell. This keeps the LED screen demonstrably usable throughout the trim and catches regressions at the step that introduced them.

### Canonical gate command

Run from the repo root on the Pi (or production-equivalent Linux + matrix), in the project venv:

```bash
sudo SPELL_MAX_SECONDS=5 /home/cde/copperdragons/.venv/bin/python spell.py void
```

executed with `cwd=led_screen/spells`. This matches how [escape-room-display/spell_runner.py](escape-room-display/spell_runner.py) launches spells (`cwd=led_screen/spells`, explicit venv interpreter, `sudo`) and how [escape-room-display/README.md](escape-room-display/README.md) documents manual invocations.

- **Working directory** must be `led_screen/spells` because [`FRAME_DATA_FOLDER = Path(f"../spell-data/{selected_spell}")`](led_screen/spells/spell.py) is resolved relative to it.
- **Privileges:** `sudo` is required for matrix GPIO access.
- **Interpreter:** use the venv Python explicitly so the gate exercises the same install you just (re)built.
- **Duration:** [`SPELL_MAX_SECONDS`](led_screen/spells/spell.py) defaults to 10s; override to 5s for fast iteration. Ctrl-C also works.

**Pass criteria:** no traceback, the void animation is visible on the panel, the process exits cleanly and the panel is cleared by the `finally: self.matrix.Clear()` block.

### Rebuild before the gate?

| After this milestone | Rebuild + reinstall first? |
|------------------------|----------------------------|
| Delete cruft dirs (`adapter/`, `bindings/c#/`, `examples-api-use/`, `utils/`, `.github/`, egg-info) | **No** — `librgbmatrix` and the editable `rgbmatrix` install are unchanged. Optionally run `make -C external/rgb-matrix build-python` if you want extra confidence the build still resolves. |
| Makefile patch (drop `examples-api-use` from `$(RGB_LIBRARY)`, fix `clean`) | **Yes** — `make -C external/rgb-matrix clean && make -C external/rgb-matrix build-python`, then `pip install -e external/rgb-matrix/bindings/python`. The gate then validates the new build graph. |
| Move `samplebase` + delete vendored `samples/` + update `scripts/setup.sh` | **Yes** — rerun the relevant `pip install` lines from the updated [scripts/setup.sh](scripts/setup.sh) (the `samples` install line must be gone). The gate then proves `from samplebase import SampleBase` resolves to [led_screen/spells/samplebase.py](led_screen/spells/samplebase.py) and frame data still loads. |
| Optional: drop Python `graphics` extension | **Yes** — reinstall `external/rgb-matrix/bindings/python`. The gate confirms `core` still loads and drives the panel. Note `void` does not exercise `rgbmatrix.graphics` (only [`runtext.py`](led_screen/spells/runtext.py) does), so a passing void gate does **not** by itself prove `runtext.py` still works after this step. |
| Vendor README trim | **No** — documentation only; rerun the gate only if you want a sanity check. |

### Per-milestone gate checkpoints

- **After `delete-cruft-dirs`:** run the gate. No rebuild required.
- **After `makefile-no-demos`:** rebuild + reinstall, then run the gate.
- **After `move-samplebase`:** apply the [scripts/setup.sh](scripts/setup.sh) edit and reinstall, then run the gate (this step is the most likely to break the spell path).
- **After `optional-graphics-ext`:** reinstall bindings, then run the gate.
- **After `vendor-readme`:** gate optional.

If any gate fails, fix the regression in that milestone before moving on.

## Verification (after implementation)

Treat these as **gates**: fix failures before merging. Order matters least for (1)–(3) on dev vs Pi; **hardware steps need a Pi** (or equivalent Linux + matrix).

### 1. Clean build and install

- Activate the project venv (same as [scripts/setup.sh](scripts/setup.sh)).
- `make -C external/rgb-matrix clean` (optional but catches stale artifacts after deleting dirs).
- `make -C external/rgb-matrix build-python` — must finish without errors; confirm `external/rgb-matrix/lib/librgbmatrix.so.1` (or `.a`) exists.
- `pip install -e external/rgb-matrix/bindings/python` — succeeds; no missing `samples` path if that install was removed from setup.

### 2. Python import sanity

- `python -c "from rgbmatrix import RGBMatrix, RGBMatrixOptions; print('ok')"` — exercises the `core` extension load against `librgbmatrix`.
- From repo root: `python -c "import sys; sys.path.insert(0, 'led_screen/spells'); from samplebase import SampleBase; print('ok')"` — confirms `samplebase` resolves without the old vendored package.

### 3. Matrix hardware smoke test (Raspberry Pi / production-like)

- Run the **canonical void gate** from the "Display gate after each milestone" section (same `sudo` + venv interpreter + `cwd=led_screen/spells` invocation). This is the same probe used between trim steps, so a clean run here confirms nothing regressed across the whole sequence.
- Then run **`sudo /home/cde/copperdragons/.venv/bin/python spell.py fireball`** from `led_screen/spells` to confirm argv parsing still selects a different spell and the second animation also plays end-to-end.

### 4. Escape-room integration (end-to-end)

- Install/run **escape-room-display** deps ([escape-room-display/requirements.txt](escape-room-display/requirements.txt)) in the same or dedicated venv as used on the Pi.
- Start the FastAPI server the way you deploy it ([escape-room-display/server.py](escape-room-display/server.py)).
- Trigger a spell swap via the real API path you use (e.g. POST/select spell) so **[spell_runner.py](escape-room-display/spell_runner.py)** starts `spell.py` with `cwd=led_screen/spells`. Confirm the display updates and logs show no spawn errors.

### 5. Developer machine without hardware (optional)

- On macOS/Windows, `scripts/setup.sh` skips the C build but still installs the editable binding; **`rgbmatrix` import may fail** — that is expected.
- Confirm **`samplebase` mock path**: run `spell.py` briefly and ensure it uses the `ImportError` mock in [led_screen/spells/samplebase.py](led_screen/spells/samplebase.py) without crashing (matrix operations no-op). Useful for CI or local sanity only, not a substitute for Pi testing.

### Success criteria summary

- **Build/install:** `make build-python` and `pip install -e bindings/python` succeed on Linux.
- **Binding load:** `from rgbmatrix import RGBMatrix, RGBMatrixOptions` works where `.so` is built.
- **Panel:** `sudo spell.py <spell>` runs on the Pi with visible output.
- **Integration:** escape-room server can swap spells and the subprocess keeps working.

## Architecture (current vs after)

```mermaid
flowchart LR
  subgraph before [Before]
    vend[vendor rgb-matrix]
    samp[vendored samples + samplebase]
    spell[spell.py]
    vend --> samp
    samp --> spell
  end

  subgraph after [After]
    lib[lib + python core only in vendor]
    sb[led_screen/spells/samplebase.py]
    spell2[spell.py]
    lib --> spell2
    sb --> spell2
  end
```
