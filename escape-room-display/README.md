# Escape room display (copperdragons)

Tiny HTTP service that lets one **master** Pi tell the **slave** Pi which spell
to animate on the LED matrix. Fits the existing `copperdragons` repo without
changing `spell.py`: it just starts/stops that script as a subprocess.

```
master (cde@copperdragons3)  --HTTP-->  slave (cde@raspberrypi)
   curl ...                          uvicorn server:app  --> spawns
                                     ~/copperdragons/led_screen/spells/spell.py
```

## On the slave: `cde@raspberrypi`

1. Copy this folder to the Pi, e.g. `~/escape-room-display`:

   ```bash
   scp -r escape-room-display cde@raspberrypi:~/
   ```

2. Install a venv (separate from the LED venv is fine, this one only runs the
   HTTP service):

   ```bash
   cd ~/escape-room-display
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Sanity-check that the underlying spell still runs:

   ```bash
   cd ~/copperdragons/led_screen/spells
   sudo /home/cde/copperdragons/.venv/bin/python spell.py void
   # Ctrl-C to stop
   ```

4. Start the HTTP service (still as `cde`, not root — `sudo` is used only for
   the spawned `spell.py` because `cde` has `NOPASSWD: ALL`):

   ```bash
   cd ~/escape-room-display
   . .venv/bin/activate
   uvicorn server:app --host 0.0.0.0 --port 8765
   ```

5. Optional: install the systemd unit to keep it running on boot:

   ```bash
   sudo cp escape-room-display.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now escape-room-display
   journalctl -u escape-room-display -f
   ```

### Firewall

If you use `ufw`, allow the port (or only allow from the Tailscale interface):

```bash
sudo ufw allow 8765/tcp
```

## On the master: `cde@copperdragons3`

Anything that can speak HTTP works; the simplest is `curl`. Use the slave's
Tailscale hostname or `100.x` IP. Example:

```bash
# start fireball
curl -sS -X POST http://raspberrypi:8765/spell \
  -H 'Content-Type: application/json' \
  -d '{"spell":"fireball"}'

# switch to void (server stops fireball first)
curl -sS -X POST http://raspberrypi:8765/spell \
  -H 'Content-Type: application/json' \
  -d '{"spell":"void"}'

# stop
curl -sS -X POST http://raspberrypi:8765/stop

# what's running
curl -sS http://raspberrypi:8765/status
```

Or use the wrapper:

```bash
./send-test.sh fireball
./send-test.sh void
./send-test.sh status
./send-test.sh stop
```

## HTTP API

| Method | Path      | Body                          | Returns                                                       |
|-------:|:----------|:------------------------------|:--------------------------------------------------------------|
| GET    | /health   | —                             | `{status, current, spells}`                                   |
| GET    | /spells   | —                             | `{spells: [...]}`                                             |
| GET    | /status   | —                             | `{current: "fireball" \| "void" \| null}`                     |
| POST   | /spell    | `{"spell":"fireball"}`        | `{ok: true, current: "fireball"}`                             |
| POST   | /stop     | —                             | `{ok: true, stopped: true\|false}`                            |

If `DISPLAY_API_KEY` is set on the slave, every request must send
`X-API-Key: <value>`.

## Config

See `env.example`. Defaults assume the layout we inspected on the slave:

- `SPELLS_DIR=/home/cde/copperdragons/led_screen/spells`
- `VENV_PYTHON=/home/cde/copperdragons/.venv/bin/python`
- `VALID_SPELLS=fireball,void`
- `USE_SUDO=1` (the Pi needs it for GPIO; set to `0` on a laptop to test the mock)

## Scaling to many puzzles

Run the same service on every puzzle Pi; the master addresses them by name,
e.g. `http://puzzle-fire:8765`, `http://puzzle-void:8765`, etc. Wiring vs Wi-Fi
does not change this — only DNS/IPs change.
