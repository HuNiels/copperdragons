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
    SPELLS_DIR          defaults to ~/copperdragons/led_screen/spells
    VENV_PYTHON         defaults to ~/copperdragons/.venv/bin/python
    VALID_SPELLS        comma-separated, default: fireball,void
    USE_SUDO            1 (default on Pi) or 0 (laptop / no GPIO)
    DISPLAY_API_KEY     if set, clients must send X-API-Key with same value

Spell subprocess env (see led_screen/spells/spell.py):
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
SPELLS_DIR = Path(os.environ.get("SPELLS_DIR", HOME / "copperdragons" / "led_screen" / "spells"))
VENV_PYTHON = Path(os.environ.get("VENV_PYTHON", HOME / "copperdragons" / ".venv" / "bin" / "python"))
VALID_SPELLS = tuple(
    s.strip() for s in os.environ.get("VALID_SPELLS", "fireball,void").split(",") if s.strip()
)
USE_SUDO = os.environ.get("USE_SUDO", "1") == "1"
API_KEY = os.environ.get("DISPLAY_API_KEY", "").strip()

runner = SpellRunner(
    spells_dir=SPELLS_DIR,
    python_exe=VENV_PYTHON,
    valid_spells=VALID_SPELLS,
    use_sudo=USE_SUDO,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "display server up: spells_dir=%s python=%s valid=%s sudo=%s api_key=%s",
        SPELLS_DIR, VENV_PYTHON, VALID_SPELLS, USE_SUDO, "set" if API_KEY else "not set",
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


@app.get("/spells")
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
    return {"ok": True, "current": current}


@app.post("/stop")
def stop(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    stopped = runner.stop()
    return {"ok": True, "stopped": stopped}
