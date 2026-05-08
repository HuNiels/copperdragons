"""Reader abstraction over pyPN5180.

This module prepends ``external/pyPN5180`` (vendored copy we edit in-tree) and
imports ``ISO14443``. The rest of the framework uses only the ``Reader``
Protocol; extend the vendored ``PN5180`` package for SPI/BUSY changes, then
adjust ``make_reader`` if the constructor or wiring changes.
"""
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from config import ScannerConfig, ScannerHardware

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "external" / "pyPN5180"))

from PN5180 import ISO14443  # noqa: E402


def recover_pn5180(reader: Reader) -> None:
    """Call PN5180 escape hatch after a BUSY timeout (ISO14443 subclasses PN5180)."""
    fn = getattr(reader, "recover_rf_off_no_busy_wait", None)
    if callable(fn):
        fn()


class Reader(Protocol):
    """Anything with an ``inventory()`` returning UID strings is a Reader."""

    def inventory(self) -> Iterable[str]: ...


class MockReader:
    """Deterministic reader for tests/dev. Returns the next scripted UID set
    on each ``inventory()`` call (the last entry repeats once exhausted)."""

    def __init__(self, scripted: list[set[str]]) -> None:
        if not scripted:
            scripted = [set()]
        self._scripted = scripted
        self._i = 0

    def inventory(self) -> list[str]:
        idx = min(self._i, len(self._scripted) - 1)
        self._i += 1
        return sorted(self._scripted[idx])


def make_reader(hw: ScannerHardware, cfg: ScannerConfig) -> Reader:
    """Build a Reader for the given scanner. Today this constructs ISO14443
    ignoring ``hw.spi_*``/``hw.busy_gpio`` (see ``external/pyPN5180`` to wire
    those through)."""
    if cfg.use_mock_readers:
        return MockReader([set()])
    try:
        # Library ``debug`` prints every SPI byte and RX_STATUS to stdout (very
        # fast/noisy). Use ``-v`` only when you need that; ``--debug`` is Python
        # logging only (see scan.py / config).
        return ISO14443(debug=cfg.verbose)
    except Exception as e:
        err = str(e).lower()
        if "gpio busy" in err:
            raise RuntimeError(
                "GPIO 25 (PN5180 BUSY) is already claimed — usually because another "
                "copy of scan.py (or any program using that pin) is still running. "
                "Check: pgrep -af scan.py  then stop the extra process (kill PID). "
                "Only one reader instance can use the PN5180 on this Pi."
            ) from e
        raise
