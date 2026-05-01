#!/usr/bin/env bash
set -e

echo "Setting up Python environment..."

python -m venv .venv

if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

python -m pip install --upgrade pip setuptools wheel

echo "Installing Python dependencies..."
pip install -r requirements.txt

# detect OS
UNAME=$(uname -s)

echo "Detected system: $UNAME"

# ONLY build rgb-matrix on Linux (Raspberry Pi / Linux machines)
if [[ "$UNAME" == "Linux"* ]]; then
    make -C external/rgb-matrix build-python || true
    pip install -e external/rgb-matrix/bindings/python
else
    echo "Installing Python-only rgb-matrix bindings (no C build)"

    pip install -e external/rgb-matrix/bindings/python
fi

echo "Setup complete!"