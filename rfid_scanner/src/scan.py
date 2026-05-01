#!/usr/bin/env python3
"""rfid_scanner CLI entrypoint.

Parses CLI args into a ``ScannerConfig`` and dispatches to one of:
- ``run_smoke_test()``       (when ``--smoke-test`` is set; no hardware/network),
- ``run_test_mode(...)``     (when ``--test-scanner ID`` is set; one reader),
- ``run_all(...)``           (default; one thread per scanner -> controller -> POST).

All real work lives in sibling modules: see ``config``, ``storage``, ``reader``,
``sender``, ``controller``, ``runner``, ``smoke_test``.
"""
from __future__ import annotations

import json
import logging

from config import build_parser, config_from_args
from controller import SpellController
from reader import Reader, make_reader
from runner import run_all, run_test_mode
from smoke_test import run_smoke_test
from storage import load_combo_spells, load_tag_spells

log = logging.getLogger("rfid")


def main() -> int:
    args = build_parser().parse_args()
    cfg = config_from_args(args)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if cfg.smoke_test:
        return run_smoke_test()

    try:
        tag_spells = load_tag_spells(cfg.tag_spells_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.error("could not load tag spells from %s: %s", cfg.tag_spells_path, e)
        return 1

    scanner_ids = {hw.scanner_id for hw in cfg.scanners}

    if cfg.test_scanner:
        if cfg.test_scanner not in scanner_ids:
            log.error(
                "--test-scanner %s is not in --scanner list (%s)",
                cfg.test_scanner,
                ",".join(sorted(scanner_ids)) or "default",
            )
            return 2
        hw = next(h for h in cfg.scanners if h.scanner_id == cfg.test_scanner)
        reader = make_reader(hw, cfg)
        return run_test_mode(cfg, hw.scanner_id, reader, tag_spells)

    try:
        combos = load_combo_spells(cfg.combo_spells_path, scanner_ids)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.error("could not load combo spells from %s: %s", cfg.combo_spells_path, e)
        return 1

    readers: dict[str, Reader] = {hw.scanner_id: make_reader(hw, cfg) for hw in cfg.scanners}
    controller = SpellController(cfg, tag_spells, combos)
    run_all(cfg, readers, controller)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
