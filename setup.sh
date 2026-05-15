#!/usr/bin/env bash
set -euo pipefail

PYTHON=${PYTHON:-python3}

# Require Python 3.10+
version=$("$PYTHON" -c 'import sys; print(sys.version_info >= (3, 10))')
if [[ "$version" != "True" ]]; then
  echo "Error: Python 3.10 or higher is required." >&2
  exit 1
fi

# Create virtualenv if it doesn't already exist
if [[ ! -d .venv ]]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi

# Activate and install dependencies
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Warn if tkinter is missing (common on Linux)
if ! "$PYTHON" -c 'import tkinter' 2>/dev/null; then
  echo
  echo "Warning: tkinter not found. Install it before running the app:"
  echo "  macOS:  brew install python-tk"
  echo "  Ubuntu: sudo apt install python3-tk"
fi

echo
echo "Setup complete. Run the app with:"
echo "  source .venv/bin/activate && python generate_image_gui.py"
