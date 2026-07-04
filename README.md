# copperdragons

Escape room puzzle: **PN5180 RFID readers** detect tagged props at fixed spots; when the **arrangement** matches a rule, a **separate Raspberry Pi** plays a matching **LED matrix animation**.

## Architecture (short)

- **Scanner Pi** (`copperdragons3`) — Raspberry Pi 4 with 2× PN5180 for POC (3 eventually; prefer all on one Pi) → run `rfid_scanner/`
- **Display Pi** (`raspberrypi`) — Raspberry Pi 4 with 32×32 RGB matrix HAT → run `escape-room-display/` + `led_screen/`
- Scanner POSTs `{"spell":"<animation>"}` to display over HTTP when combos match

```
Scanner Pi  --POST /spell-->  Display Pi  -->  LED animation
```

## Documentation

| Doc | Audience |
|-----|----------|
| [AGENTS.md](AGENTS.md) | AI assistants — read first to avoid wrong assumptions |
| [docs/PROJECT.md](docs/PROJECT.md) | Full project overview, terminology, data flow |
| [rfid_scanner/README.md](rfid_scanner/README.md) | PN5180 wiring, scanner setup, combo config |
| [escape-room-display/README.md](escape-room-display/README.md) | Display HTTP API, systemd, deployment |

## Quick start

**Display Pi:**

```bash
cd escape-room-display && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8765
```

**Scanner Pi:**

```bash
./scripts/setup.sh   # or see rfid_scanner/README.md for Pi-specific venv
python rfid_scanner/src/scan.py --display-url http://<display-pi>:8765
```

## Repo layout

- `rfid_scanner/` — NFC scanning and combo logic
- `escape-room-display/` — HTTP control plane for the LED node
- `led_screen/` — animation runner and frame data
- `external/` — vendored pyPN5180 and rgb-matrix
- `utils/` — offline GIF → frame JSON conversion
