"""Configuration: per-scanner hardware identity, runtime settings dataclass,
CLI parser, and Namespace -> ScannerConfig mapping.

No business logic lives here; this module is pure plumbing between argparse
and the rest of the framework."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

SCAN_DIR = Path(__file__).resolve().parents[1]


@dataclass
class ScannerHardware:
    """Per-scanner hardware identity. SPI/BUSY fields are placeholders for a
    future pyPN5180 patch; today's library ignores them."""

    scanner_id: str
    spi_bus: int = 0
    spi_device: int = 0
    busy_gpio: int = 25


@dataclass
class ScannerConfig:
    """Runtime settings for the scanner framework (no argparse here)."""

    verbose: bool
    interval: float
    display_url: str
    default_spell: str
    tag_spells_path: Path
    combo_spells_path: Path
    spell_cooldown: float
    display_timeout: float
    api_key: str | None
    quiet_polls: bool
    log_misses: bool
    bind_timeout: float
    no_bind_prompt: bool
    scanners: list[ScannerHardware] = field(default_factory=list)
    test_scanner: str | None = None
    smoke_test: bool = False
    use_mock_readers: bool = False
    debug_logging: bool = False
    log_file: Path | None = None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Multi-scanner RFID framework: per-scanner threads report to a "
            "controller that POSTs a spell when the combined per-scanner state "
            "matches a configured combo. --test-scanner ID runs one reader in "
            "per-tag mode for hardware validation."
        ),
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "PN5180 library trace to stdout: each SPI write as 'Sent Frame' (hex bytes), "
            "plus RX_STATUS/IRQ_STATUS after reads. Very fast/noisy; use for hardware bring-up."
        ),
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Python logging at DEBUG (every poll line, cooldown skips in test mode). "
            "Does not enable SPI dump; add -v separately if you need wire-level trace."
        ),
    )
    ap.add_argument(
        "--log-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="append the same log lines to this file (UTF-8)",
    )
    ap.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="seconds between inventory polls (default 0.1); increase e.g. 0.5 to slow logs",
    )
    ap.add_argument(
        "--display-url",
        default="http://raspberrypi:8765",
        help="escape-room-display base URL (default http://raspberrypi:8765)",
    )
    ap.add_argument(
        "--spell",
        default="fireball",
        help="default spell when a UID is not listed in the tag map (default fireball)",
    )
    ap.add_argument(
        "--scanner",
        action="append",
        default=None,
        metavar="ID",
        help=(
            "scanner id (repeat or comma-separate, e.g. --scanner A --scanner B "
            "or --scanner A,B); default: a single scanner named 'default'"
        ),
    )
    ap.add_argument(
        "--test-scanner",
        default=None,
        metavar="ID",
        help=(
            "single-scanner test mode: run only this scanner with per-tag "
            "behavior (UID -> spell from tag_spells.json, with binding prompt). "
            "If --scanner is omitted, the scanner list defaults to this id."
        ),
    )
    ap.add_argument(
        "--tag-spells",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "JSON file mapping tag UID (hex, e.g. 63aa5531) to element/spell name; "
            f"default: {SCAN_DIR / 'tag_spells.json'} if that file exists"
        ),
    )
    ap.add_argument(
        "--combo-spells",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "JSON file with [{match: {scanner: element, ...}, spell: ...}] combos; "
            f"default: {SCAN_DIR / 'combo_spells.json'} if that file exists"
        ),
    )
    ap.add_argument(
        "--spell-cooldown",
        type=float,
        default=60.0,
        metavar="SEC",
        help="minimum seconds between spell POSTs for the same combo / tag UID (default 60)",
    )
    ap.add_argument(
        "--display-timeout",
        type=float,
        default=5.0,
        help="HTTP timeout seconds for display POSTs (default 5)",
    )
    ap.add_argument(
        "--api-key",
        default="",
        help="optional X-API-Key if DISPLAY_API_KEY is set on the slave",
    )
    ap.add_argument(
        "--quiet-polls",
        action="store_true",
        help="do not log poll hit/miss lines",
    )
    ap.add_argument(
        "--log-misses",
        action="store_true",
        help="log poll: miss on empty inventory (noisy; default off)",
    )
    ap.add_argument(
        "--bind-timeout",
        type=float,
        default=5.0,
        metavar="SEC",
        help="seconds to wait for spell name when binding a new tag (default 5)",
    )
    ap.add_argument(
        "--no-bind-prompt",
        action="store_true",
        help="do not prompt for unknown tags; use default spell only",
    )
    ap.add_argument(
        "--mock-readers",
        action="store_true",
        help="use empty MockReaders instead of real PN5180 hardware (dev only)",
    )
    ap.add_argument(
        "--smoke-test",
        action="store_true",
        help="run an in-process MockReader smoke test of the controller and exit",
    )
    return ap


def config_from_args(args: argparse.Namespace) -> ScannerConfig:
    tag_spells_path = args.tag_spells if args.tag_spells is not None else SCAN_DIR / "tag_spells.json"
    combo_spells_path = (
        args.combo_spells if args.combo_spells is not None else SCAN_DIR / "combo_spells.json"
    )
    api_key = args.api_key.strip() or None

    # Test mode only runs one reader; if the user did not pass --scanner, align
    # the implicit list with --test-scanner so `--test-scanner A` works alone.
    raw_ids = args.scanner or ["default"]
    if args.test_scanner is not None and args.scanner is None:
        raw_ids = [args.test_scanner]
    seen: set[str] = set()
    scanners: list[ScannerHardware] = []
    for entry in raw_ids:
        for sid in (s.strip() for s in entry.split(",")):
            if not sid or sid in seen:
                continue
            seen.add(sid)
            scanners.append(ScannerHardware(scanner_id=sid))

    return ScannerConfig(
        verbose=args.verbose,
        interval=args.interval,
        display_url=args.display_url,
        default_spell=args.spell,
        tag_spells_path=tag_spells_path,
        combo_spells_path=combo_spells_path,
        spell_cooldown=args.spell_cooldown,
        display_timeout=args.display_timeout,
        api_key=api_key,
        quiet_polls=args.quiet_polls,
        log_misses=args.log_misses,
        bind_timeout=args.bind_timeout,
        no_bind_prompt=args.no_bind_prompt,
        scanners=scanners,
        test_scanner=args.test_scanner,
        smoke_test=args.smoke_test,
        use_mock_readers=args.mock_readers,
        debug_logging=args.debug,
        log_file=args.log_file,
    )
