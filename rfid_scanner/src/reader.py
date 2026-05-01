"""Reader abstraction over pyPN5180.

This module owns the vendored-pyPN5180 sys.path setup and the import of
``ISO14443``. Everything else in the framework talks only to the ``Reader``
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

from PN5180 import ISO14443  # noqa: E402


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
    ignoring ``hw.spi_*``/``hw.busy_gpio``; when pyPN5180 is patched to accept
    those, this is the only place that needs to change."""
    if cfg.use_mock_readers:
        return MockReader([set()])
    return ISO14443(debug=cfg.verbose)
