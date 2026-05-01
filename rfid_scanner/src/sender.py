"""HTTP POST of a spell to the escape-room-display slave.

Two layers:
- ``post_spell``: thin urllib wrapper, no logging.
- ``send_spell_to_slave``: logs the attempt and outcome, returns True on
  success. Used by the controller (combo mode) and runner (test mode).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from config import ScannerConfig

log = logging.getLogger("rfid")


def post_spell(
    base_url: str,
    spell: str,
    api_key: str | None,
    timeout: float,
) -> tuple[int, float]:
    url = base_url.rstrip("/") + "/spell"
    payload = json.dumps({"spell": spell}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()
        status = int(resp.status)
    elapsed_s = time.perf_counter() - t0
    return status, elapsed_s


def send_spell_to_slave(cfg: ScannerConfig, source: str, spell: str, kind: str = "slave") -> bool:
    """POST the spell to ``cfg.display_url``/spell. ``source`` is logged as the
    originating context (a UID for test mode, a combo description for combo
    mode). ``kind`` tags the log line, e.g. ``slave``/``combo``/``test``."""
    spell_url = cfg.display_url.rstrip("/") + "/spell"
    log.info("display -> POST %s source=%s spell=%s (%s)", spell_url, source, spell, kind)
    try:
        status, elapsed_s = post_spell(cfg.display_url, spell, cfg.api_key, cfg.display_timeout)
        log.info("display <- slave OK HTTP %s in %.0f ms", status, elapsed_s * 1000)
        return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:300]
        log.warning("display <- slave HTTP %s: %s", e.code, err_body or e.reason)
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log.warning("display <- slave failed (spell): %s", e)
        return False
