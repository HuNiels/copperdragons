#!/usr/bin/env python3
"""Poll ISO 14443-A tags on the PN5180; POST the display spell when a tag is
seen and that tag's spell cooldown has elapsed.

Optional JSON mapping (see ``tag_spells.example.json``): hex UID → spell name.
An unknown UID on a TTY prompts once to bind a spell and writes ``tag_spells.json``.
Use ``--no-bind-prompt`` for headless/default-only behavior.

Each outer poll runs a single ``inventory()`` and logs ``poll: hit`` when a
UID is seen. Optional ``--log-misses`` also logs empty polls.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import select
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "external" / "pyPN5180"))

from PN5180 import ISO14443  # noqa: E402

log = logging.getLogger("rfid")

_SCAN_DIR = Path(__file__).resolve().parent


def _load_tag_spells(path: Path) -> dict[str, str]:
    """Load UID → spell map from JSON; missing file → empty map."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("tag spells file must be a JSON object mapping UID to spell name")
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        if not key:
            continue
        spell = str(v).strip()
        if spell:
            out[key] = spell
    return out


def _spell_for_uid(uid: str, tag_spells: dict[str, str], default_spell: str) -> str:
    return tag_spells.get(uid.strip().lower(), default_spell)


def _save_tag_spells(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(sorted(mapping.items())), indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _prompt_new_tag_spell(uid: str, timeout: float) -> str | None:
    """Read one line from stdin within timeout; None if timeout or empty skip."""
    sys.stderr.write(
        f"\nNew tag UID {uid} — type spell name to save "
        f"(empty Enter = skip, {timeout:.0f}s timeout)\nSpell: "
    )
    sys.stderr.flush()
    try:
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
    except InterruptedError:
        return None
    if not ready:
        sys.stderr.write("(timed out)\n")
        sys.stderr.flush()
        return None
    line = sys.stdin.readline()
    if not line:
        return None
    spell = line.strip()
    return spell if spell else None


def _post_spell(
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-v", "--verbose", action="store_true", help="library debug logs (SPI frames, IRQ state)"
    )
    ap.add_argument(
        "--interval", type=float, default=0.1, help="seconds between inventory polls (default 0.1)"
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
        "--tag-spells",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "JSON file mapping tag UID (hex, e.g. 63aa5531) to spell name; "
            f"default: {_SCAN_DIR / 'tag_spells.json'} if that file exists"
        ),
    )
    ap.add_argument(
        "--spell-cooldown",
        type=float,
        default=60.0,
        metavar="SEC",
        help=(
            "minimum seconds between spell POSTs for the same tag UID (default 60)"
        ),
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
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    tag_spells_path = args.tag_spells
    if tag_spells_path is None:
        tag_spells_path = _SCAN_DIR / "tag_spells.json"
    try:
        tag_spells = _load_tag_spells(tag_spells_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.error("could not load tag spells from %s: %s", tag_spells_path, e)
        return 1

    reader = ISO14443(debug=args.verbose)
    last_spell_at: dict[str, float] = {}
    binding_prompted: set[str] = set()
    api_key = args.api_key.strip() or None

    stop = False

    def _stop(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info(
        "scanner up; display=%s default_spell=%s tag_spells=%s (%d uid(s)) spell_cooldown=%ss; Ctrl-C to quit",
        args.display_url,
        args.spell,
        tag_spells_path,
        len(tag_spells),
        args.spell_cooldown,
    )
    try:
        while not stop:
            try:
                uids = set(reader.inventory())
            except Exception:
                log.exception("inventory failed")
                time.sleep(args.interval)
                continue

            if not args.quiet_polls:
                if uids:
                    log.info("poll: hit uids=%s", ",".join(sorted(uids)))
                elif args.log_misses:
                    log.info("poll: miss")

            if not uids:
                time.sleep(args.interval)
                continue

            primary_uid = sorted(uids)[0]
            if len(uids) > 1:
                log.warning(
                    "multiple tags in field (%s); using uid %s for spell",
                    ",".join(sorted(uids)),
                    primary_uid,
                )

            uid_key = primary_uid.strip().lower()
            if (
                uid_key not in tag_spells
                and uid_key not in binding_prompted
            ):
                binding_prompted.add(uid_key)
                if args.no_bind_prompt:
                    pass
                elif not sys.stdin.isatty():
                    log.warning(
                        "unknown tag %s — not in %s; "
                        "run in a terminal to bind, or edit JSON",
                        uid_key,
                        tag_spells_path,
                    )
                else:
                    log.info(
                        "unknown tag %s — waiting up to %ss for spell name",
                        uid_key,
                        args.bind_timeout,
                    )
                    chosen = _prompt_new_tag_spell(uid_key, args.bind_timeout)
                    if chosen:
                        tag_spells[uid_key] = chosen
                        try:
                            _save_tag_spells(tag_spells_path, tag_spells)
                            log.info(
                                "saved binding %s -> %s in %s",
                                uid_key,
                                chosen,
                                tag_spells_path,
                            )
                        except OSError as e:
                            del tag_spells[uid_key]
                            binding_prompted.discard(uid_key)
                            log.error("could not save tag spells file: %s", e)
                    else:
                        log.info(
                            "no binding saved for %s; using default spell %s",
                            uid_key,
                            args.spell,
                        )

            spell_name = _spell_for_uid(primary_uid, tag_spells, args.spell)
            now = time.monotonic()
            last = last_spell_at.get(primary_uid)
            cooldown_ok = last is None or (now - last >= args.spell_cooldown)
            if cooldown_ok:
                spell_url = args.display_url.rstrip("/") + "/spell"
                log.info(
                    "display -> POST %s uid=%s spell=%s (slave)",
                    spell_url,
                    primary_uid,
                    spell_name,
                )
                try:
                    status, elapsed_s = _post_spell(
                        args.display_url,
                        spell_name,
                        api_key,
                        args.display_timeout,
                    )
                    last_spell_at[primary_uid] = time.monotonic()
                    log.info(
                        "display <- slave OK HTTP %s in %.0f ms",
                        status,
                        elapsed_s * 1000,
                    )
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode(errors="replace")[:300]
                    log.warning(
                        "display <- slave HTTP %s: %s",
                        e.code,
                        err_body or e.reason,
                    )
                except (urllib.error.URLError, OSError, TimeoutError) as e:
                    log.warning("display <- slave failed (spell): %s", e)

            time.sleep(args.interval)
    finally:
        log.info("scanner down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
