"""Worker threads and top-level orchestration.

- ``scan_one``: pure inventory loop for one scanner; reports to a controller.
- ``run_all``: spawns one ``scan_one`` thread per scanner; SIGINT/SIGTERM-safe.
- ``run_test_mode``: single-scanner per-tag behavior for hardware validation
  (no controller, no threads, no combo logic)."""
from __future__ import annotations

import logging
import signal
import threading
import time

from config import ScannerConfig, ScannerHardware
from controller import SpellController
from reader import Reader, recover_pn5180
from sender import send_spell_to_slave
from storage import handle_unknown_tag

log = logging.getLogger("rfid")


def scan_one(
    hw: ScannerHardware,
    reader: Reader,
    cfg: ScannerConfig,
    controller: SpellController,
    stop: threading.Event,
) -> None:
    """Pure inventory loop for one scanner. Reports to the controller; never
    decides on spells or talks HTTP."""
    log.info("scanner[%s] up", hw.scanner_id)
    try:
        while not stop.is_set():
            try:
                # Log before inventory: poll lines only appeared after inventory()
                # returned, so a blocking PN5180/BUSY wait looked like "no logging".
                log.debug("scanner[%s] inventory starting", hw.scanner_id)
                uids = set(reader.inventory())
            except KeyboardInterrupt:
                raise
            except RuntimeError as e:
                if "BUSY stayed high" in str(e):
                    log.warning(
                        "scanner[%s] PN5180 BUSY timeout — RF_OFF recovery (check power/heat/wiring if this repeats)",
                        hw.scanner_id,
                    )
                    try:
                        recover_pn5180(reader)
                    except Exception:
                        log.exception("scanner[%s] PN5180 recovery failed", hw.scanner_id)
                    stop.wait(cfg.interval)
                    continue
                log.exception("scanner[%s] inventory failed", hw.scanner_id)
                stop.wait(cfg.interval)
                continue
            except Exception:
                log.exception("scanner[%s] inventory failed", hw.scanner_id)
                stop.wait(cfg.interval)
                continue

            log.debug(
                "scanner[%s] poll uids=%s",
                hw.scanner_id,
                ",".join(sorted(uids)) if uids else "-",
            )

            if not cfg.quiet_polls:
                if uids:
                    log.info("scanner[%s] poll: hit uids=%s", hw.scanner_id, ",".join(sorted(uids)))
                elif cfg.log_misses:
                    log.info("scanner[%s] poll: miss", hw.scanner_id)

            controller.update(hw.scanner_id, uids)
            stop.wait(cfg.interval)
    finally:
        log.info("scanner[%s] down", hw.scanner_id)


def run_all(
    cfg: ScannerConfig,
    readers: dict[str, Reader],
    controller: SpellController,
) -> None:
    """Spawn one worker thread per scanner; install signal handlers; join."""
    stop = threading.Event()

    def _stop(*_: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info(
        "framework up; scanners=%s display=%s combos=%d cooldown=%ss; Ctrl-C to quit",
        ",".join(hw.scanner_id for hw in cfg.scanners),
        cfg.display_url,
        controller.combo_count,
        cfg.spell_cooldown,
    )

    threads: list[threading.Thread] = []
    for hw in cfg.scanners:
        t = threading.Thread(
            target=scan_one,
            args=(hw, readers[hw.scanner_id], cfg, controller, stop),
            name=f"scanner-{hw.scanner_id}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    try:
        while not stop.is_set():
            stop.wait(0.5)
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=cfg.interval * 5 + 1.0)
        log.info("framework down")


def run_test_mode(cfg: ScannerConfig, scanner_id: str, reader: Reader, tag_spells: dict[str, str]) -> int:
    """Single scanner in per-tag mode: UID -> spell from tag_spells, optional
    binding prompt, per-UID cooldown. No combo evaluation, no threading."""
    last_spell_at: dict[str, float] = {}
    binding_prompted: set[str] = set()

    # Do not override SIGINT: the default raises KeyboardInterrupt on the main
    # thread so Ctrl-C exits without waiting for a full inventory() round trip.
    # A custom handler that only set a flag made shutdown depend on inventory()
    # returning, which feels like "Ctrl-C does nothing" when the reader is slow
    # or stuck inside pyPN5180.
    def _sigterm(_sig: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _sigterm)

    log.info(
        "test-mode up; scanner=%s display=%s default_spell=%s tag_spells=%s (%d uid(s)) cooldown=%ss; Ctrl-C to quit",
        scanner_id,
        cfg.display_url,
        cfg.default_spell,
        cfg.tag_spells_path,
        len(tag_spells),
        cfg.spell_cooldown,
    )
    try:
        while True:
            try:
                log.debug("scanner[%s] inventory starting", scanner_id)
                uids = set(reader.inventory())
            except KeyboardInterrupt:
                raise
            except RuntimeError as e:
                if "BUSY stayed high" in str(e):
                    log.warning(
                        "scanner[%s] PN5180 BUSY timeout — RF_OFF recovery (check power/heat/wiring if this repeats)",
                        scanner_id,
                    )
                    try:
                        recover_pn5180(reader)
                    except Exception:
                        log.exception("PN5180 recovery failed")
                    time.sleep(cfg.interval)
                    continue
                log.exception("test-mode inventory failed")
                time.sleep(cfg.interval)
                continue
            except Exception:
                log.exception("test-mode inventory failed")
                time.sleep(cfg.interval)
                continue

            log.debug(
                "scanner[%s] poll uids=%s",
                scanner_id,
                ",".join(sorted(uids)) if uids else "-",
            )

            if not cfg.quiet_polls:
                if uids:
                    log.info("scanner[%s] poll: hit uids=%s", scanner_id, ",".join(sorted(uids)))
                elif cfg.log_misses:
                    log.info("scanner[%s] poll: miss", scanner_id)

            if not uids:
                time.sleep(cfg.interval)
                continue

            sorted_uids = sorted(uids)
            primary_uid = sorted_uids[0]
            uid = primary_uid.strip().lower()
            if len(uids) > 1:
                log.warning(
                    "multiple tags in field (%s); using uid %s for spell",
                    ",".join(sorted_uids),
                    primary_uid,
                )

            if uid not in tag_spells and uid not in binding_prompted:
                binding_prompted.add(uid)
                handle_unknown_tag(
                    uid,
                    tag_spells,
                    cfg.tag_spells_path,
                    cfg.bind_timeout,
                    cfg.no_bind_prompt,
                    cfg.default_spell,
                    binding_prompted,
                )

            spell_name = tag_spells.get(uid, cfg.default_spell)
            now = time.monotonic()
            last = last_spell_at.get(primary_uid)
            if last is not None and (now - last < cfg.spell_cooldown):
                log.debug(
                    "test-mode: cooldown skip uid=%s (%.1fs left)",
                    primary_uid,
                    cfg.spell_cooldown - (now - last),
                )
                time.sleep(cfg.interval)
                continue
            if send_spell_to_slave(cfg, primary_uid, spell_name, kind="test"):
                last_spell_at[primary_uid] = time.monotonic()

            time.sleep(cfg.interval)
    except KeyboardInterrupt:
        log.info("interrupted (Ctrl-C or SIGTERM)")
    finally:
        log.info("test-mode down")
    return 0
