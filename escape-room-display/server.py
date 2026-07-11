"""
HTTP control plane for a single escape-room LED node (the `copperdragons`
`led_screen` on the slave Pi: cde@raspberrypi).

Call from the master (cde@copperdragons3) with plain `curl`. One master can
fan out to many slaves by POSTing to each node URL.

Run (on the slave):
    cd ~/escape-room-display
    . .venv/bin/activate
    uvicorn server:app --host 0.0.0.0 --port 8765

Env (all optional):
    SPELL_RUNNER_DIR    cwd for animate_spell.py (default ~/copperdragons/led_screen/spell_runner)
    SPELL_DATA_DIR      frame JSON folders for spell whitelist (default .../spell_data)
    SPELLS_DIR          legacy alias for SPELL_RUNNER_DIR
    VENV_PYTHON         defaults to ~/copperdragons/.venv/bin/python
    VALID_SPELLS        comma-separated whitelist; if unset, names match folders in
                        SPELL_DATA_DIR (same as animate_spell.py). If missing/empty,
                        falls back to fireball,void
    USE_SUDO            1 (default on Pi) or 0 (laptop / no GPIO)
    DISPLAY_API_KEY     if set, clients must send X-API-Key with same value

Spell subprocess env (see led_screen/spell_runner/animate_spell.py):
    SPELL_LOOPS         how many times to loop the full frame sequence (default 5)
    SPELL_MAX_SECONDS   wall-clock cap in seconds (default 10); stops early if reached before all loops finish
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from spell_runner import SpellRunner

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HOME = Path(os.path.expanduser("~"))


def _spells_from_spell_data(spell_data_dir: Path) -> tuple[str, ...]:
    """Folder names under spell-data, same rule as led_screen/spell_data/spell.py."""
    if not spell_data_dir.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in spell_data_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )
    )


_LED_SCREEN = HOME / "copperdragons" / "led_screen"
SPELL_RUNNER_DIR = Path(
    os.environ.get(
        "SPELL_RUNNER_DIR",
        os.environ.get("SPELLS_DIR", _LED_SCREEN / "spell_runner"),
    )
).expanduser()
SPELL_DATA_DIR = Path(
    os.environ.get("SPELL_DATA_DIR", _LED_SCREEN / "spell_data")
).expanduser()
VENV_PYTHON = Path(
    os.environ.get("VENV_PYTHON", HOME / "copperdragons" / ".venv" / "bin" / "python")
).expanduser()
_valid_env = os.environ.get("VALID_SPELLS", "").strip()
if _valid_env:
    VALID_SPELLS = tuple(s.strip() for s in _valid_env.split(",") if s.strip())
else:
    VALID_SPELLS = _spells_from_spell_data(SPELL_DATA_DIR.resolve())
    if not VALID_SPELLS:
        VALID_SPELLS = ("fireball", "void")
USE_SUDO = os.environ.get("USE_SUDO", "1") == "1"
API_KEY = os.environ.get("DISPLAY_API_KEY", "").strip()

runner = SpellRunner(
    spells_dir=SPELL_RUNNER_DIR,
    python_exe=VENV_PYTHON,
    valid_spells=VALID_SPELLS,
    use_sudo=USE_SUDO,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "display server up: runner_dir=%s spell_data=%s python=%s valid=%s sudo=%s api_key=%s",
        SPELL_RUNNER_DIR,
        SPELL_DATA_DIR,
        VENV_PYTHON,
        VALID_SPELLS,
        USE_SUDO,
        "set" if API_KEY else "not set",
    )
    try:
        yield
    finally:
        runner.stop()
        log.info("display server down")


app = FastAPI(title="Escape room display (copperdragons)", version="0.1.0", lifespan=lifespan)


class SpellRequest(BaseModel):
    spell: str = Field(..., min_length=1, max_length=64, description="Spell name, e.g. 'fireball' or 'void'")


def _check_api_key(x_api_key: str | None) -> None:
    if not API_KEY:
        return
    if (x_api_key or "").strip() != API_KEY:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "current": runner.current(),
        "spells": runner.list_spells(),
    }


@app.get("/spell_data")
def spells() -> dict[str, Any]:
    return {"spells": runner.list_spells()}


@app.get("/status")
def status() -> dict[str, Any]:
    return {"current": runner.current()}


@app.post("/spell")
def start_spell(
    body: SpellRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    try:
        current = runner.start(body.spell)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, "current": current}


@app.post("/stop")
def stop(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    stopped = runner.stop()
    return {"ok": True, "stopped": stopped}
