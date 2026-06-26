#!/usr/bin/env python3
"""PN5180 wiring sanity check for the copperdragons RFID scanner.

Run on the Raspberry Pi next to the PN5180 (SPI0 / CE0, BUSY on BCM GPIO 25).

What it checks
--------------
- ``/dev/spidev0.0`` exists and can be opened (SPI enabled; user in ``spi`` group).
- BCM GPIO 25 (physical pin 22) can be read — this must match the module BUSY line.
- Minimal PN5180 SPI exchange: READ_REGISTER for IRQ_STATUS and SYSTEM_STATUS.

Passing does not guarantee NFC range or antenna tuning; failing usually means
wrong pin, loose jumper, bad ground, or missing power.

Usage::

    python rfid_scanner/check_pn5180_wiring.py
    python rfid_scanner/check_pn5180_wiring.py -v

Requires the same environment as ``scan.py`` (``spidev``, ``RPi.GPIO``/lgpio).
"""
from __future__ import annotations

import argparse
import grp
import os
import sys
import time


def _groups() -> set[str]:
    out = set()
    for gid in os.getgroups():
        try:
            out.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("What it checks")[0].strip())
    ap.add_argument("-v", "--verbose", action="store_true", help="print hex dumps")
    ap.add_argument(
        "--busy-timeout",
        type=float,
        default=15.0,
        metavar="SEC",
        help="max seconds to wait for BUSY low per step (default 15)",
    )
    args = ap.parse_args()
    verbose = args.verbose
    busy_timeout = args.busy_timeout

    SPIDEV_PATH = "/dev/spidev0.0"
    BCM_BUSY = 25
    HEADER_BUSY_PIN = 22

    # --- Preflight ---
    ok = True
    print("=== PN5180 wiring check ===\n")

    if not os.path.exists(SPIDEV_PATH):
        print(f"FAIL: {SPIDEV_PATH} missing — enable SPI (raspi-config / dtparam=spi=on) and reboot.")
        return 1

    if "spi" not in _groups() and os.access(SPIDEV_PATH, os.R_OK | os.W_OK) is False:
        print(
            "WARN: current user may lack SPI access — try: sudo usermod -aG spi $USER "
            "(then log out and back in). Continuing if open succeeds…"
        )

    try:
        import spidev  # type: ignore[import-untyped]
        import RPi.GPIO as GPIO  # type: ignore[import-untyped]
    except ImportError as e:
        print(f"FAIL: import error ({e}). Install spidev and RPi.GPIO (see rfid_scanner/README.md).")
        return 1

    PN5180_READ_REGISTER = 0x04
    IRQ_STATUS = 0x02
    SYSTEM_STATUS = 0x24

    def wait_busy(gpio: object, label: str) -> None:
        """Wait until BCM GPIO 25 is LOW (PN5180 not BUSY)."""
        deadline = time.monotonic() + busy_timeout
        if gpio.input(BCM_BUSY):
            while gpio.input(BCM_BUSY):
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        f"{label}: BUSY stayed HIGH >{busy_timeout:.0f}s on BCM GPIO {BCM_BUSY} "
                        f"(header pin {HEADER_BUSY_PIN}). "
                        "Wire module BUSY → pin 22; check 3.3 V logic, SPI, and power."
                    )
                time.sleep(0.01)

    def xfer(gpio: object, frame: list[int], tag: str) -> None:
        wait_busy(gpio, tag + " (before TX)")
        spi.writebytes(frame)
        wait_busy(gpio, tag + " (after TX)")

    spi = None
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BCM_BUSY, GPIO.IN)

        lvl = GPIO.input(BCM_BUSY)
        print(f"GPIO {BCM_BUSY} (header pin {HEADER_BUSY_PIN}, BUSY): reads {'HIGH' if lvl else 'LOW'}")
        print("(idle level varies; stuck HIGH forever usually means wrong/floating BUSY.)\n")

        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 50000
        spi.mode = 0

        print(f"Opened SPI bus 0 device 0 ({SPIDEV_PATH}), 50 kHz\n")

        def read_register(reg_addr: int, name: str) -> list[int]:
            xfer(GPIO, [PN5180_READ_REGISTER, reg_addr], f"READ_REGISTER {name}")
            data = spi.readbytes(4)
            if verbose:
                print(f"  READ_REGISTER {name} (0x{reg_addr:02x}) -> {[hex(b) for b in data]}")
            return list(data)

        print("Probing PN5180 registers over SPI…")
        irq = read_register(IRQ_STATUS, "IRQ_STATUS")
        sysst = read_register(SYSTEM_STATUS, "SYSTEM_STATUS")

        bad_irq = all(b == 0 for b in irq) or all(b == 0xFF for b in irq)
        bad_sys = all(b == 0 for b in sysst) or all(b == 0xFF for b in sysst)
        if bad_irq and bad_sys:
            print(
                "\nWARN: reads look like open MISO (all 0x00 or 0xFF). "
                "Check MOSI→MOSI, MISO→MISO, SCK, CE0→NSS, common GND."
            )
            ok = False
        else:
            print(f"\nOK: IRQ_STATUS bytes = {irq}")
            print(f"OK: SYSTEM_STATUS bytes = {sysst}")
            print("\nPASS: SPI + BUSY path responded like a PN5180.")

        GPIO.cleanup()
        spi.close()
        return 0 if ok else 2

    except RuntimeError as e:
        print(f"\nFAIL: {e}")
        try:
            GPIO.cleanup()
        except Exception:
            pass
        if spi is not None:
            try:
                spi.close()
            except Exception:
                pass
        return 3
    except PermissionError as e:
        print(f"\nFAIL: permission ({e}). Use ``spi`` group or run with sufficient rights.")
        try:
            GPIO.cleanup()
        except Exception:
            pass
        return 1
    except OSError as e:
        print(f"\nFAIL: OS error ({e}). SPI/GPIO may be in use by another process — stop scan.py first.")
        try:
            GPIO.cleanup()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
