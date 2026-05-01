# PN5180 RFID scanner (copperdragons)

A multi-scanner framework for PN5180 modules over SPI. Each scanner runs in its
own thread, polls ISO 14443-A tags (MIFARE Classic/Ultralight, NTAG, most NFC
stickers), and reports to a controller. The controller `POST`s a spell to the
[`escape-room-display`](../escape-room-display/) HTTP API when the *combined*
per-scanner state matches a configured combo. A single-scanner test mode is
provided for hardware validation; see
[tag_spells.example.json](tag_spells.example.json) and
[combo_spells.example.json](combo_spells.example.json).

> Caveat: pyPN5180 currently hard-codes SPI bus 0 / device 0 and BUSY GPIO 25
> (see section 1). Multi-PN5180 hardware on a single Pi will need a follow-up
> patch to the vendored library; the software framework here is ready for it
> via a `Reader` factory.

Uses [fservida/pyPN5180](https://github.com/fservida/pyPN5180), vendored at
[`external/pyPN5180/`](../external/pyPN5180/) alongside the existing
`external/rgb-matrix/` checkout.

## 1. Wiring (PN5180 module -> Raspberry Pi 4)

The library hard-codes SPI bus 0 / device 0 (`CE0`) and BUSY on BCM `GPIO 25`.
RESET and IRQ are not driven in software, so tie `RST` high and leave `IRQ`
disconnected.

| PN5180 pin        | Pi header pin | Pi signal           | Notes                                |
| ----------------- | ------------- | ------------------- | ------------------------------------ |
| `3.3V` (logic)    | 1             | 3V3                 |                                      |
| `5V`  (TVDD / RF) | 2             | 5V                  | only needed on dual-rail breakouts   |
| `GND`             | 6             | GND                 |                                      |
| `MOSI`            | 19            | GPIO 10 (SPI0_MOSI) |                                      |
| `MISO`            | 21            | GPIO 9  (SPI0_MISO) |                                      |
| `SCK`             | 23            | GPIO 11 (SPI0_SCLK) |                                      |
| `NSS` / `SS`      | 24            | GPIO 8  (SPI0_CE0)  |                                      |
| `BUSY`            | 22            | GPIO 25             | hard-coded in the library            |
| `RST`             | 17            | 3V3 (tie high)      | or a free GPIO if you want SW reset  |
| `IRQ`             | -             | -                   | leave disconnected                   |

Keep the SPI wires short (<= ~15 cm) and routed away from the antenna loop.
pyPN5180 runs SPI at 50 kHz for reliability, so cable quality is forgiving.

If your breakout has a single 5V input with onboard regulators, connect only
5V + GND for supply and skip the 3V3 rail.

## 2. One-time Pi setup

Enable SPI and confirm the device node exists:

```bash
sudo raspi-config nonint do_spi 0   # or set dtparam=spi=on in /boot/firmware/config.txt
sudo reboot
ls /dev/spidev0.*                   # should show /dev/spidev0.0
```

Make sure your user can reach SPI and GPIO without sudo:

```bash
sudo usermod -aG spi,gpio "$USER"   # log out / back in after this
```

## 3. Install & run

On Raspberry Pi OS Bookworm / Trixie the Python packages we need (`spidev`,
`gpiozero`, and a `RPi.GPIO`-compatible shim) ship as apt packages and should
be consumed from there; upstream `RPi.GPIO` does not build on Python 3.13, and
`lgpio` needs `swig` to build from source, so `pip install` is fragile.

On this scanner Pi the venv is created fresh with `--system-site-packages`:

```bash
sudo apt install python3-spidev python3-gpiozero python3-rpi-lgpio
python3 -m venv --system-site-packages /home/cde/copperdragons/.venv
source /home/cde/copperdragons/.venv/bin/activate

# No-op on a Pi that already has the apt packages; useful elsewhere.
pip install -r rfid_scanner/requirements.txt
```

Note: the other node's venv at `../escape-room-display/` is a different venv
on a different Pi; we just reuse the same `/home/cde/copperdragons/.venv`
path convention.

Run it:

```bash
cd /home/cde/copperdragons
python rfid_scanner/src/scan.py                      # one scanner named "default", combo mode
python rfid_scanner/src/scan.py -v                   # plus library SPI/IRQ trace
python rfid_scanner/src/scan.py --scanner A,B        # two scanners "A" and "B", combo mode
python rfid_scanner/src/scan.py --test-scanner A     # single scanner "A" in test mode
python rfid_scanner/src/scan.py --smoke-test         # in-process MockReader self-check, then exit
```

Typical combo-mode options when pointing at the display Pi:

```bash
python rfid_scanner/src/scan.py \
  --scanner A --scanner B \
  --display-url http://raspberrypi:8765 \
  --tag-spells rfid_scanner/tag_spells.json \
  --combo-spells rfid_scanner/combo_spells.json \
  --spell-cooldown 60
```

Expected output (timestamps abbreviated):

```
INFO framework up; scanners=A,B display=http://raspberrypi:8765 combos=2 cooldown=60s; Ctrl-C to quit
INFO scanner[A] up
INFO scanner[B] up
INFO scanner[A] poll: hit uids=63aa5531
INFO controller: A - -> fire (uid=63aa5531)
INFO scanner[B] poll: hit uids=b2f28804
INFO controller: B - -> ice (uid=b2f28804)
INFO controller: combo {A=fire, B=ice} -> void
INFO display -> POST http://raspberrypi:8765/spell source={A=fire, B=ice} spell=void (combo)
INFO display <- slave OK HTTP 200 in 12 ms
```

Ctrl-C exits cleanly (`framework down` is logged).

### How combos work

Two JSON files drive the framework:

1. [tag_spells.json](tag_spells.example.json) — `{ UID: element }`. Maps each
   physical tag to a short element name (e.g. `fire`, `ice`).
2. [combo_spells.json](combo_spells.example.json) — list of
   `{ "match": { scanner_id: element, ... }, "spell": ... }` rules. The
   controller fires the named spell only when **every** scanner has a tag in
   its field and the resulting state matches a `match` exactly. Per-scanner
   pairing is significant: `{A: fire, B: ice}` and `{A: ice, B: fire}` can map
   to different spells.

The controller fires once per state transition (no spamming while the state
is held) and respects `--spell-cooldown` per combo.

### Test mode (single scanner)

`--test-scanner ID` runs only that scanner with the legacy per-tag behavior:

- `tag_spells.json` is treated as `{ UID: spell }` (the element name *is* the
  spell), and the spell is POSTed directly on tag presence.
- An unknown UID on a TTY prompts once to bind a spell to
  `tag_spells.json`. `--no-bind-prompt` disables this for headless setups.
- Per-UID cooldown via `--spell-cooldown` (same as the original single-scanner
  script).

Use this to validate one PN5180 at a time without touching combo logic.

## 4. Troubleshooting

- `FileNotFoundError: [Errno 2] No such file or directory: '/dev/spidev0.0'`
  SPI is not enabled. Run the `raspi-config` step in section 2 and reboot.
- `PermissionError` on `/dev/spidev0.0` or `/dev/gpiochip*`
  Your user is not in the `spi` / `gpio` groups yet, or you did not re-login
  after `usermod`. Check with `groups`.
- `ModuleNotFoundError: No module named 'RPi'` (or `'lgpio'`, `'spidev'`)
  Your venv was created without `--system-site-packages`. Recreate it per
  section 3, or install the apt packages and rerun.
- `error: command 'swig' failed` when pip-installing `lgpio`
  Same root cause: use the apt `python3-lgpio` package instead of building
  from source, which is what `--system-site-packages` gets you.
- "Card Not Ready - Waiting for Busy Low" printed forever (with `-v`)
  BUSY is not wired, or wired to the wrong GPIO. It must go to physical pin 22
  (BCM GPIO 25) - the library does not let you change this.
- No tags ever detected, but no errors
  Check that you are tapping an ISO 14443-A card (MIFARE/NTAG). ISO 15693
  cards will not show up in this script; use `ISO15693` from the same library
  for those.
- Intermittent reads / garbage UIDs
  Shorten the SPI wires; the PN5180's antenna is sensitive to stray
  capacitance from long jumper leads.

## 5. What this does not do (yet)

- Drive multiple PN5180s on a single Pi at the hardware level. The
  framework supports N scanners in software (one thread each), but pyPN5180
  hard-codes SPI bus/device and BUSY GPIO. Until the vendored library is
  patched to accept those as constructor args, multi-PN5180 hardware is not
  supported. Use `--mock-readers` for software-side testing in the meantime.
- Software reset of the PN5180 (would need `RST` on a GPIO and a pulse via
  `gpiozero.DigitalOutputDevice` before constructing the reader).
- Auto-start on boot. If you want that, copy the pattern from
  [`../escape-room-display/escape-room-display.service`](../escape-room-display/escape-room-display.service).
