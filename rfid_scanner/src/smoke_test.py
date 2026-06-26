"""In-process smoke test: drive the SpellController through a scripted state
machine and assert each combo fires exactly once per state transition.

The controller's HTTP sender is replaced with a recording stub via the
``sender`` constructor argument, so this test never touches the network and
never monkey-patches module globals."""
from __future__ import annotations

import logging
from pathlib import Path

from config import ScannerConfig, ScannerHardware
from controller import ComboKey, SpellController

log = logging.getLogger("rfid")


def run_smoke_test() -> int:
    cfg = ScannerConfig(
        verbose=False,
        interval=0.0,
        display_url="http://example.invalid",
        default_spell="none",
        tag_spells_path=Path("/dev/null"),
        combo_spells_path=Path("/dev/null"),
        spell_cooldown=0.0,
        display_timeout=1.0,
        api_key=None,
        quiet_polls=True,
        log_misses=False,
        bind_timeout=0.0,
        no_bind_prompt=True,
        scanners=[ScannerHardware("A"), ScannerHardware("B")],
    )
    tag_spells = {"aaaa": "fire", "bbbb": "ice", "cccc": "ice", "dddd": "fire"}
    combos: dict[ComboKey, str] = {
        frozenset({("A", "fire"), ("B", "ice")}): "void",
        frozenset({("A", "ice"), ("B", "fire")}): "fireblast",
    }
    sent: list[tuple[str, str, str]] = []

    def fake_send(_cfg: ScannerConfig, source: str, spell: str, kind: str = "slave") -> bool:
        sent.append((source, spell, kind))
        return True

    controller = SpellController(cfg, tag_spells, combos, sender=fake_send)
    controller.update("A", {"aaaa"})
    controller.update("B", {"bbbb"})
    controller.update("B", {"bbbb"})
    controller.update("A", set())
    controller.update("B", set())
    controller.update("A", {"cccc"})
    controller.update("B", {"dddd"})

    spells_cast = [(spell, kind) for _src, spell, kind in sent]
    expected = [("void", "combo"), ("fireblast", "combo")]
    if spells_cast != expected:
        log.error("smoke-test FAIL: expected %s got %s", expected, spells_cast)
        return 1
    log.info("smoke-test OK: %s", spells_cast)
    return 0
