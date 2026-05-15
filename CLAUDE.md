# CLAUDE.md

## Project overview

Single-file Python desktop GUI (`generate_image_gui.py`) for batch image generation via the Gemini API. Uses tkinter for the UI and stores the API key in the macOS Keychain via `keyring`.

## Environment setup

```bash
bash setup.sh          # creates .venv, installs deps, checks Python 3.10+ and tkinter
source .venv/bin/activate
```

Re-run `setup.sh` after pulling changes to pick up any new dependencies.

## Running the app

```bash
python generate_image_gui.py
```

No CLI arguments. The GUI handles all configuration.

## Key files

| File | Purpose |
|---|---|
| `generate_image_gui.py` | Entire application — UI, API calls, key management |
| `requirements.txt` | Third-party deps: `google-genai`, `keyring`, `Pillow` |
| `setup.sh` | One-command venv setup |

## Architecture

- **`App(tk.Tk)`** — single class, all UI and logic lives here.
- **Threading model**: the tkinter main loop runs on the main thread. Generation runs in a `threading.Thread`; individual image requests run inside a `ThreadPoolExecutor`. All UI updates from background threads go through `self.after(0, ...)` — never call tkinter widgets directly from a non-main thread.
- **Update check**: runs in a daemon thread at startup (`_check_for_update`). Hits the GitHub Releases API, compares tags with `_parse_version` (uses `re.findall` to handle pre-release suffixes like `-beta`), and logs a link if a newer version exists. Failures print to `stderr` and do not surface in the UI.
- **API key**: stored in the macOS Keychain under service `gemini-image-gen` / username `api_key`. Never written to disk in plain text.

## Versioning

Bump `__version__` in `generate_image_gui.py` and cut a GitHub Release with a matching tag (e.g. `v1.1.0`) to trigger update notifications for existing users.

## Dependencies

All third-party deps are in `requirements.txt`. `tkinter`, `re`, `json`, `urllib.request`, `threading`, `subprocess`, and `concurrent.futures` are stdlib — do not add them to `requirements.txt`.

## Style notes

- Python 3.10+ syntax (`str | None`, `tuple[int, ...]`) is fine.
- No comments unless the reason is non-obvious. No docstrings beyond the module-level one.
- Keep all logic in `generate_image_gui.py` — avoid splitting into multiple files unless the app grows significantly.
