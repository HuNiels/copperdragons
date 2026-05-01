# PN5180 RFID scanner (copperdragons)

A tiny standalone script that uses a PN5180 module over SPI to print the UIDs
of any ISO 14443-A tags (MIFARE Classic/Ultralight, NTAG, most NFC stickers)
that come near the antenna.

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
python rfid_scanner/scan.py            # normal console output
python rfid_scanner/scan.py -v         # plus library SPI/IRQ trace
python rfid_scanner/scan.py --interval 0.1   # poll faster
```

Expected output when you tap a MIFARE card on the antenna:

```
2026-04-24 17:10:02 INFO scanner up; Ctrl-C to quit
2026-04-24 17:10:04 INFO TAG ENTER 04a224fa9b6e80
2026-04-24 17:10:06 INFO TAG LEAVE 04a224fa9b6e80
```

Ctrl-C exits cleanly.

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

- Trigger anything on the [`escape-room-display`](../escape-room-display/) LED
  node -- this script only logs. Mapping UIDs -> spells can live in a later
  change.
- Software reset of the PN5180 (would need `RST` on a GPIO and a pulse via
  `gpiozero.DigitalOutputDevice` before constructing the reader).
- Auto-start on boot. If you want that, copy the pattern from
  [`../escape-room-display/escape-room-display.service`](../escape-room-display/escape-room-display.service).
