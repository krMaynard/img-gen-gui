# img-gen-gui

A lightweight desktop GUI for batch image generation using the Gemini API. Enter a prompt, choose how many images to generate, and the app fires all requests in parallel and saves the results as PNGs.

## Features

- **Batch generation** — generate 1–10 images from a single prompt in parallel
- **Secure API key storage** — key is saved to the macOS Keychain via `keyring`; never stored in plain text
- **Configurable output folder** — defaults to `~/Desktop/genai`, browseable from the UI
- **Live log** — dark-themed scrollable log shows model responses and saved file paths as they arrive
- **Auto-open on macOS** — each saved image is opened in Preview automatically
- **Update notifications** — checks GitHub Releases on startup and logs a link if a newer version is available

## Requirements

- Python 3.10+
- macOS (Keychain integration; the rest of the app is cross-platform)
- A [Google AI Studio](https://aistudio.google.com/) API key with access to `gemini-3-pro-image-preview`

## Installation

```bash
git clone https://github.com/krmaynard/img-gen-gui.git
cd img-gen-gui
bash setup.sh
```

`setup.sh` creates a `.venv` virtualenv, installs dependencies, and prints the launch command. Run it once; re-run after pulling updates.

`tkinter` ships with the standard library. If it is missing on your system, install it via your package manager (e.g., `brew install python-tk` on macOS).

## Usage

```bash
source .venv/bin/activate
python generate_image_gui.py
```

1. Click **Set key** and paste your Google API key. It is stored in the Keychain and only needs to be entered once.
2. Edit the prompt in the text box.
3. Set the **Images** spinner to the number of images you want (1–10).
4. Optionally change the **Output folder**.
5. Click **Generate**. Progress is shown in the log; images open automatically when saved.

## Updating

The app checks for new releases on startup and prints a link to the log if one is available.

To apply an update:

```bash
git pull
bash setup.sh
```

## Configuration

| Constant | Default | Description |
|---|---|---|
| `__version__` | `1.0.0` | Current version; bump when cutting a release |
| `MODEL_NAME` | `gemini-3-pro-image-preview` | Gemini model used for generation |
| `KEYRING_SERVICE` | `gemini-image-gen` | Keychain service name |
| `DEFAULT_PROMPT` | language-learning flowchart | Pre-filled prompt shown on launch |

All constants are at the top of `generate_image_gui.py`.

## How it works

Each generation request calls `client.models.generate_content` with `response_modalities=["TEXT", "IMAGE"]`. The model returns interleaved text and image parts; text is printed to the log and image data is decoded from the inline bytes and saved as a PNG via Pillow. All requests for a given batch share a single `ThreadPoolExecutor` so they run concurrently. The update check runs in a separate daemon thread at startup so it never blocks the UI.

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Gemini API client |
| `keyring` | Secure credential storage |
| `Pillow` | Decoding and saving PNG images |
| `tkinter` | GUI (stdlib) |
