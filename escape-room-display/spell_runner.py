"""
Manage the lifecycle of a single running `spell.py` subprocess.

Why subprocess: `spell.py` owns the RGB matrix. It loops the animation SPELL_LOOPS
times (default 5) or until SPELL_MAX_SECONDS, clears the panel, and exits. POST /spell
still replaces any
running spell by killing the old process first.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class SpellRunner:
    def __init__(
        self,
        spells_dir: Path,
        python_exe: Path,
        valid_spells: tuple[str, ...],
        use_sudo: bool = True,
    ) -> None:
        self.spells_dir = Path(spells_dir)
        self.python_exe = Path(python_exe)
        self.valid_spells = tuple(valid_spells)
        self.use_sudo = use_sudo
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._current: Optional[str] = None

    def list_spells(self) -> list[str]:
        return list(self.valid_spells)

    def current(self) -> Optional[str]:
        with self._lock:
            if self._proc is None:
                return None
            if self._proc.poll() is not None:
                self._current = None
                self._proc = None
            return self._current

    def start(self, spell: str) -> str:
        if spell not in self.valid_spells:
            raise ValueError(f"unknown spell {spell!r}; valid: {self.valid_spells}")
        with self._lock:
            self._stop_locked()
            cmd: list[str] = []
            if self.use_sudo:
                cmd += ["sudo", "-n"]
            cmd += [str(self.python_exe), "spell.py", spell]
            log.info("starting spell=%s cmd=%s cwd=%s", spell, cmd, self.spells_dir)
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(self.spells_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._current = spell
            return spell

    def stop(self) -> bool:
        with self._lock:
            return self._stop_locked()

    def _stop_locked(self) -> bool:
        if self._proc is None:
            return False
        if self._proc.poll() is not None:
            self._proc = None
            self._current = None
            return False
        try:
            if self.use_sudo:
                # child was started via sudo, so it's owned by root; use sudo kill
                subprocess.run(
                    ["sudo", "-n", "kill", "-TERM", f"-{self._proc.pid}"],
                    check=False,
                )
            else:
                os.killpg(self._proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                if self.use_sudo:
                    subprocess.run(
                        ["sudo", "-n", "kill", "-KILL", f"-{self._proc.pid}"],
                        check=False,
                    )
                else:
                    os.killpg(self._proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._proc.wait(timeout=3)
        self._proc = None
        self._current = None
        return True
