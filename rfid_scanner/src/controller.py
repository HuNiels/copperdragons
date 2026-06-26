"""SpellController: tracks each scanner's current element and triggers a
combo POST when the full per-scanner state both matches a known combo and
represents a transition (no spamming while held). Per-combo cooldown.

The HTTP sender is injected via the constructor so tests can substitute a
fake without monkey-patching module globals."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from config import ScannerConfig
from sender import send_spell_to_slave

log = logging.getLogger("rfid")

ComboKey = frozenset[tuple[str, str]]
SpellSender = Callable[[ScannerConfig, str, str, str], bool]


def format_state(state: dict[str, str | None]) -> str:
    return "{" + ", ".join(f"{k}={v}" for k, v in sorted(state.items())) + "}"


class SpellController:
    """Tracks per-scanner state under a lock and casts spells on transitions
    into a configured combo, subject to per-combo cooldown."""

    def __init__(
        self,
        cfg: ScannerConfig,
        tag_spells: dict[str, str],
        combos: dict[ComboKey, str],
        sender: SpellSender = send_spell_to_slave,
    ) -> None:
        self._cfg = cfg
        self._tag_spells = tag_spells
        self._combos = combos
        self._sender = sender
        self._state: dict[str, str | None] = {hw.scanner_id: None for hw in cfg.scanners}
        self._lock = threading.Lock()
        self._last_combo: ComboKey | None = None
        self._last_cast_at: dict[ComboKey, float] = {}

    @property
    def combo_count(self) -> int:
        return len(self._combos)

    def _resolve_element(self, uids: set[str]) -> tuple[str | None, str | None]:
        """Returns (primary_uid, element). Element is ``None`` when the field
        is empty or the primary UID is not in ``tag_spells``."""
        if not uids:
            return None, None
        primary_uid = sorted(uids)[0]
        elem = self._tag_spells.get(primary_uid.strip().lower())
        return primary_uid, elem

    def update(self, scanner_id: str, uids: set[str]) -> None:
        primary_uid, element = self._resolve_element(uids)

        with self._lock:
            if scanner_id not in self._state:
                log.warning("controller: ignoring update from unknown scanner %s", scanner_id)
                return
            prev = self._state[scanner_id]
            self._state[scanner_id] = element
            if prev != element:
                log.info(
                    "controller: %s %s -> %s%s",
                    scanner_id,
                    prev or "-",
                    element or "-",
                    f" (uid={primary_uid})" if primary_uid else "",
                )

            if any(v is None for v in self._state.values()):
                self._last_combo = None
                return

            combo_key: ComboKey = frozenset(
                (sid, elem) for sid, elem in self._state.items() if elem is not None
            )

            if combo_key == self._last_combo:
                return

            spell = self._combos.get(combo_key)
            if spell is None:
                log.info("controller: no combo for %s", format_state(self._state))
                self._last_combo = combo_key
                return

            now = time.monotonic()
            last_cast = self._last_cast_at.get(combo_key)
            if last_cast is not None and (now - last_cast) < self._cfg.spell_cooldown:
                log.info(
                    "controller: combo %s -> %s suppressed (cooldown %.1fs)",
                    format_state(self._state),
                    spell,
                    self._cfg.spell_cooldown - (now - last_cast),
                )
                self._last_combo = combo_key
                return

            log.info("controller: combo %s -> %s", format_state(self._state), spell)
            cfg = self._cfg
            source = format_state(self._state)

        if self._sender(cfg, source, spell, "combo"):
            with self._lock:
                self._last_cast_at[combo_key] = time.monotonic()
                self._last_combo = combo_key
