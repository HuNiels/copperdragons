"""Reader abstraction over pyPN5180.

This module owns the vendored-pyPN5180 sys.path setup and the import of
``ISO14443`` / ``ISO15693``. Everything else in the framework talks only to the ``Reader``
Protocol below; when pyPN5180 is patched/forked to support per-scanner SPI
device + BUSY GPIO, ``make_reader`` is the only function that needs updating.
"""
from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from config import ScannerConfig, ScannerHardware

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "external" / "pyPN5180"))

from PN5180 import ISO14443, ISO15693  # noqa: E402


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
    """Build a Reader for the given scanner. Today this constructs ISO14443 or
    ISO15693 per ``cfg.protocol``, ignoring ``hw.spi_*``/``hw.busy_gpio``; when
    pyPN5180 is patched to accept those, this is the only place that needs to change."""
    if cfg.use_mock_readers:
        return MockReader([set()])
    reader_cls = ISO15693 if cfg.protocol == "15693" else ISO14443
    try:
        # Library ``debug`` prints every SPI byte and RX_STATUS to stdout (very
        # fast/noisy). Use ``-v`` only when you need that; ``--debug`` is Python
        # logging only (see scan.py / config).
        return reader_cls(debug=cfg.verbose)
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
