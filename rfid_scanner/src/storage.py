"""JSON I/O for tag_spells and combo_spells, plus the interactive binding
prompt used by test mode for unknown UIDs."""
from __future__ import annotations

import json
import logging
import os
import select
import sys
from pathlib import Path

from controller import ComboKey

log = logging.getLogger("rfid")


def load_tag_spells(path: Path) -> dict[str, str]:
    """Load UID -> element/spell map from JSON; missing file -> empty map."""
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


def save_tag_spells(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(sorted(mapping.items())), indent=2, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_combo_spells(path: Path, known_scanner_ids: set[str]) -> dict[ComboKey, str]:
    """Load combo rules: list of ``{"match": {scanner: element, ...}, "spell": str}``.

    Returns ``{frozenset((scanner, element), ...): spell}`` for O(1) lookup.
    Missing file logs a one-line warning and returns an empty dict.
    """
    if not path.is_file():
        log.warning("no combo file at %s; combos disabled", path)
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("combo spells file must be a JSON list of {match, spell} entries")
    combos: dict[ComboKey, str] = {}
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or "match" not in entry or "spell" not in entry:
            raise ValueError(f"combo entry {i} must have 'match' and 'spell' fields")
        match = entry["match"]
        if not isinstance(match, dict) or not match:
            raise ValueError(f"combo entry {i}: 'match' must be a non-empty object")
        pairs: list[tuple[str, str]] = []
        for sid, elem in match.items():
            sid_s = str(sid).strip()
            elem_s = str(elem).strip().lower()
            if not sid_s or not elem_s:
                raise ValueError(f"combo entry {i}: empty scanner id or element")
            if sid_s not in known_scanner_ids:
                log.warning(
                    "combo entry %d references unknown scanner %r (known: %s)",
                    i, sid_s, ",".join(sorted(known_scanner_ids)),
                )
            pairs.append((sid_s, elem_s))
        spell = str(entry["spell"]).strip()
        if not spell:
            raise ValueError(f"combo entry {i}: empty 'spell'")
        combos[frozenset(pairs)] = spell
    return combos


def prompt_new_tag_spell(uid: str, timeout: float) -> str | None:
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


def handle_unknown_tag(
    uid: str,
    tag_spells: dict[str, str],
    path: Path,
    bind_timeout: float,
    no_bind_prompt: bool,
    default_spell: str,
    binding_prompted: set[str],
) -> None:
    """Test-mode UX: on a TTY, prompt once to bind a new UID and persist it."""
    if no_bind_prompt:
        return
    if not sys.stdin.isatty():
        log.warning(
            "unknown tag %s — not in %s; "
            "run in a terminal to bind, or edit JSON",
            uid,
            path,
        )
        return
    log.info("unknown tag %s — waiting up to %ss for spell name", uid, bind_timeout)
    chosen = prompt_new_tag_spell(uid, bind_timeout)
    if not chosen:
        log.info("no binding saved for %s; using default spell %s", uid, default_spell)
        return
    tag_spells[uid] = chosen
    try:
        save_tag_spells(path, tag_spells)
        log.info("saved binding %s -> %s in %s", uid, chosen, path)
    except OSError as e:
        del tag_spells[uid]
        binding_prompted.discard(uid)
        log.error("could not save tag spells file: %s", e)
