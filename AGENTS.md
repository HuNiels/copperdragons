# AI context — copperdragons

Read this before making assumptions about this repo.

## What this project is

An **escape room puzzle**: players place physical props (NFC-tagged items) at fixed spots on a **table**. **PN5180 RFID readers** detect which **element** each item represents. When the **combination** across all spots matches a rule, a **separate Raspberry Pi** drives a **32×32 RGB LED matrix (HAT)** to play a matching animation (“spell”).

Players also have a physical **spellbook** in the room (analog, not software) that shows which item combinations cast which spells.

This is **embedded Pi software**, not a web app, cloud service, or game engine.

## Hardware layout

```
┌─────────────────────────────┐     HTTP POST      ┌──────────────────────────────┐
│  Scanner Pi                 │  ───────────────►  │  Display Pi                  │
│  cde@copperdragons3         │  /spell {"spell":…}│  cde@raspberrypi             │
│  Raspberry Pi 4             │                    │  Raspberry Pi 4              │
│  + 2× PN5180 (POC; 3 later) │                    │  + 32×32 RGB matrix HAT      │
│  rfid_scanner/              │                    │  escape-room-display/        │
│                             │                    │  → led_screen/ (animation)   │
└─────────────────────────────┘                    └──────────────────────────────┘
```

- **One scanner Pi** (preferred) runs all readers for the table. Readers sit **next to each other on the same table** — goal is **2 readers on 1 Pi** for POC (3 readers eventually), pending pyPN5180 multi-device support.
- **One display Pi** runs `escape-room-display/` and renders animations via `led_screen/`.
- Pis talk over the network (e.g. Tailscale). Scanner POSTs to `http://raspberrypi:8765/spell`.

## Terminology

| Term | Meaning |
|------|---------|
| **Element** | What a physical item represents (e.g. `fire`, `air`, `ice`). Mapped from NFC UID in `tag_spells.json`. |
| **Combo** | A full arrangement of elements across all scanners that matches a rule in `combo_spells.json`. Example: fire + air → `fireball`. |
| **Spell** | The outcome of a successful combo. **Today:** an LED animation only. **Future (out of scope):** physical room effects (e.g. “conjure clothes” drops clothing). Do not build room-actuator integration unless asked. |
| **Tag / UID** | ISO 14443-A NFC sticker on a physical prop. Scanned by PN5180. |

Config chain (production target): **UID → element → combo match → spell (animation name)**.

## Current vs target

| | **Now (test mode)** | **Target (combo mode)** |
|--|---------------------|-------------------------|
| CLI | `--test-scanner A` (one reader at a time) | Default `scan.py` with multiple `--scanner` IDs |
| `tag_spells.json` | UID → **spell** name directly (e.g. `"63aa5531": "fireball"`) | UID → **element** (e.g. `"63aa5531": "fire"`) |
| Combo rules | Not used | `combo_spells.json` maps element arrangement → spell |
| Why | Hardware bring-up, validating reader → display path | Full puzzle: fire + air → fireball |

**Do not assume combo mode is live.** The checked-in `tag_spells.json` reflects current test mode. Combo logic exists in code but is not what we run in the room yet.

## Player-visible behaviour

*(Production target — combo mode not live yet.)*

- **No default animation.** Idle = blank/off panel.
- When a combo matches, the spell animation plays; when it **finishes**, the panel returns to **idle** (not a looping attract mode).
- Wrong or incomplete arrangements → nothing happens.
- The in-room **spellbook** (physical prop) is the player-facing reference for valid combinations — not a digital UI in this repo.

**Test mode today:** placing a tagged item on the one active reader triggers its mapped spell directly (no combo required).

## Software flow

**Test mode (current):** one scanner thread → UID lookup in `tag_spells.json` → POST spell to display Pi.

**Combo mode (target):**

1. Each PN5180 runs in its own thread (`rfid_scanner/src/runner.py`), polling for tags.
2. UID → element via `tag_spells.json`.
3. `SpellController` (`controller.py`) tracks per-scanner state; when **all** scanners have a known element and the state matches a combo, it POSTs once (transition-only, with cooldown).
4. Display Pi `escape-room-display/server.py` receives POST `/spell`, spawns the animation subprocess, stops any running animation first.
5. `led_screen/spell_runner/animate_spell.py` loads frame JSON from `led_screen/spell_data/<spell>/` and drives the matrix via vendored `external/rgb-matrix/`.

## Scale

| Phase | Readers | Scanner Pi layout |
|-------|---------|-------------------|
| POC | 2 | Prefer 1 Pi, 2 readers (blocked on pyPN5180 multi-device) |
| Production (likely) | 3 | Prefer 1 Pi, 3 readers |

## Repository layout

| Path | Role |
|------|------|
| `rfid_scanner/` | PN5180 scanning, combo logic, HTTP client to display Pi |
| `escape-room-display/` | FastAPI HTTP server on the display Pi; subprocess lifecycle |
| `led_screen/` | Animation runner + pre-rendered frame data (`spell_data/`) |
| `utils/convert-image-to-rgb/` | Offline tool: GIF → frame JSON (not runtime) |
| `external/pyPN5180/` | Vendored PN5180 SPI library |
| `external/rgb-matrix/` | Vendored hzeller/rpi-rgb-led-matrix bindings |
| `scripts/setup.sh` | Pi setup: venv + rgb-matrix build |

Per-component setup: `rfid_scanner/README.md`, `escape-room-display/README.md`.

## Common wrong assumptions

1. **Single Pi for everything** — Scanner and display are **separate machines**. Only the multiple *readers* should share one scanner Pi.
2. **Combo mode is not live** — We run **`--test-scanner`** today: one tag → one spell. Combo logic is implemented but not deployed. Do not “fix” `tag_spells.json` to use elements until we switch modes.
3. **Default / idle animation** — There is none. Idle is blank.
4. **Spells trigger room hardware** — Not yet. Spells = LED animations only for now.
5. **UID → spell in tag_spells.json is correct for now** — That file maps UIDs to spell names because we're in test mode. Production will use UID → element + `combo_spells.json`.
6. **Path names in older docs** — Some docs/READMEs still say `led_screen/spells/spell.py` and `spell-data`. **In this repo:** `led_screen/spell_runner/animate_spell.py` and `led_screen/spell_data/`. Verify paths before editing.
7. **Multi-PN5180 on one Pi** — This is the **preferred** deployment (readers on same table), but vendored pyPN5180 **hard-codes** SPI bus 0 / CE0 and BUSY GPIO 25. Library patch needed before 2–3 readers on one Pi is realistic.
8. **Realtime graphics** — Animations are **pre-baked JSON grids**, not procedurally generated at runtime.
9. **Rewrite `external/`** — Treat as vendored upstream. Trim only with intent (see `docs/plans/trim-rgb-matrix-vendor.md`).
10. **Web frontend** — No player-facing UI. Physical spellbook + LED matrix only.

## What is not implemented yet

- **Combo mode deployment** — code exists; room still runs `--test-scanner` (UID → spell).
- Multiple PN5180s on one Pi (hardware/library limitation — high priority for this project).
- Physical spell effects (clothing drop, etc.).
- Other outputs (audio, relays).
- Auto-start systemd unit for `rfid_scanner` (pattern exists in `escape-room-display/escape-room-display.service`).

## When changing things

- **New animation:** add folder under `led_screen/spell_data/<name>/` with `*-frame_*.json` and `*-colours.json`.
- **New combo:** edit `tag_spells.json` (UID → element) and `combo_spells.json` (element arrangement → spell).
- **Keep subprocess contract:** display server spawns an animation script from configured `SPELLS_DIR` with a spell name argv.
