#!/usr/bin/env python3
"""GUI for Gemini image generation with API key stored in the system keychain."""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from tkinter import filedialog, messagebox, simpledialog, ttk

import keyring
from google import genai
from google.genai import types
from PIL import Image

__version__ = "1.0.0"

MODEL_NAME = "gemini-3-pro-image-preview"
KEYRING_SERVICE = "gemini-image-gen"
KEYRING_USERNAME = "api_key"
RELEASES_API = "https://api.github.com/repos/krmaynard/img-gen-gui/releases/latest"

DEFAULT_PROMPT = (
    "Create a clear, professional flowchart diagram illustrating a language "
    "learning workflow with: LLM generating text, translating, TTS creating "
    "audio, LLM building vocabulary lists, and an image model creating "
    "illustrated vocabulary cards. Show these steps in a repeating cycle."
)


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", tag))


def load_api_key() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)


def save_api_key(key: str):
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)


def delete_api_key():
    keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gemini Image Generator")
        self.resizable(False, False)
        self._build_ui()
        self._refresh_key_status()
        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # --- API key row ---
        key_frame = ttk.LabelFrame(self, text="API Key (macOS Keychain)")
        key_frame.grid(row=0, column=0, sticky="ew", **pad)

        self.key_status = ttk.Label(key_frame, text="")
        self.key_status.grid(row=0, column=0, sticky="w", padx=8, pady=4)

        btn_frame = ttk.Frame(key_frame)
        btn_frame.grid(row=0, column=1, padx=8)
        ttk.Button(btn_frame, text="Set key", command=self._set_key).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Remove", command=self._remove_key).pack(side="left", padx=2)

        # --- Prompt ---
        ttk.Label(self, text="Prompt:").grid(row=1, column=0, sticky="w", padx=10)
        self.prompt_text = tk.Text(self, width=60, height=6, wrap="word")
        self.prompt_text.grid(row=2, column=0, padx=10, pady=(0, 4), sticky="ew")
        self.prompt_text.insert("1.0", DEFAULT_PROMPT)

        # --- Input images ---
        img_frame = ttk.LabelFrame(self, text="Input images (optional)")
        img_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        img_frame.columnconfigure(0, weight=1)

        self.input_images: list[str] = []
        list_frame = ttk.Frame(img_frame)
        list_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        list_frame.columnconfigure(0, weight=1)
        self.img_listbox = tk.Listbox(list_frame, height=3, activestyle="none")
        self.img_listbox.grid(row=0, column=0, sticky="ew")
        img_scroll = ttk.Scrollbar(list_frame, command=self.img_listbox.yview)
        self.img_listbox.configure(yscrollcommand=img_scroll.set)
        img_scroll.grid(row=0, column=1, sticky="ns")

        img_btns = ttk.Frame(img_frame)
        img_btns.grid(row=0, column=1, padx=8, sticky="n")
        ttk.Button(img_btns, text="Add…", command=self._add_input_images).pack(fill="x", pady=1)
        ttk.Button(img_btns, text="Remove", command=self._remove_input_image).pack(fill="x", pady=1)
        ttk.Button(img_btns, text="Clear", command=self._clear_input_images).pack(fill="x", pady=1)

        # --- Options row ---
        opts = ttk.Frame(self)
        opts.grid(row=4, column=0, sticky="ew", padx=10, pady=4)

        ttk.Label(opts, text="Images:").pack(side="left")
        self.count_var = tk.IntVar(value=1)
        ttk.Spinbox(opts, from_=1, to=10, width=4, textvariable=self.count_var).pack(side="left", padx=(4, 16))

        ttk.Label(opts, text="Output folder:").pack(side="left")
        self.out_dir_var = tk.StringVar(value=os.path.expanduser("~/Pictures/genai"))
        ttk.Entry(opts, textvariable=self.out_dir_var, width=28).pack(side="left", padx=4)
        ttk.Button(opts, text="Browse…", command=self._browse).pack(side="left")

        # --- Generate button ---
        self.gen_btn = ttk.Button(self, text="Generate", command=self._start_generation)
        self.gen_btn.grid(row=5, column=0, pady=6)

        # --- Progress bar ---
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=400)
        self.progress.grid(row=6, column=0, padx=10, pady=(0, 4))

        # --- Log ---
        ttk.Label(self, text="Log:").grid(row=7, column=0, sticky="w", padx=10)
        log_frame = ttk.Frame(self)
        log_frame.grid(row=8, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.log = tk.Text(log_frame, width=60, height=8, state="disabled", bg="#1e1e1e", fg="#d4d4d4")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- Update check --

    def _check_for_update(self):
        try:
            req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "img-gen-gui"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                return
            if _parse_version(latest_tag) > _parse_version(__version__):
                url = data.get("html_url", RELEASES_API)
                self.after(
                    0,
                    self._log,
                    f"Update available: {latest_tag} (you have v{__version__}) — {url}",
                )
        except Exception as e:
            print(f"Update check failed: {e}", file=sys.stderr)

    # -- Key management --

    def _refresh_key_status(self):
        key = load_api_key()
        if key:
            self.key_status.config(text=f"Stored: {'*' * 8}{key[-4:]}", foreground="green")
        else:
            self.key_status.config(text="No key stored", foreground="red")

    def _set_key(self):
        key = simpledialog.askstring("API Key", "Enter your Google API key:", show="*", parent=self)
        if key and key.strip():
            save_api_key(key.strip())
            self._refresh_key_status()
            self._log("API key saved to keychain.")

    def _remove_key(self):
        if messagebox.askyesno("Remove key", "Remove API key from keychain?"):
            try:
                delete_api_key()
            except keyring.errors.PasswordDeleteError:
                pass
            self._refresh_key_status()
            self._log("API key removed.")

    # -- Folder picker --

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if path:
            self.out_dir_var.set(path)

    # -- Input images --

    def _add_input_images(self):
        paths = filedialog.askopenfilenames(
            title="Select input images",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        for p in paths:
            if p not in self.input_images:
                self.input_images.append(p)
                self.img_listbox.insert("end", os.path.basename(p))

    def _remove_input_image(self):
        sel = self.img_listbox.curselection()
        for i in reversed(sel):
            self.img_listbox.delete(i)
            del self.input_images[i]

    def _clear_input_images(self):
        self.img_listbox.delete(0, "end")
        self.input_images.clear()

    # -- Generation --

    def _log(self, msg: str):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _start_generation(self):
        api_key = load_api_key()
        if not api_key:
            messagebox.showerror("No API key", "Set your API key first.")
            return

        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showerror("Empty prompt", "Enter a prompt before generating.")
            return

        count = self.count_var.get()
        out_dir = self.out_dir_var.get()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create output directory: {e}")
            return

        input_paths = list(self.input_images)
        try:
            input_images = [Image.open(p) for p in input_paths]
            for img in input_images:
                img.load()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open input image: {e}")
            return

        self.gen_btn.config(state="disabled")
        self.progress.start(12)
        threading.Thread(
            target=self._run_generation,
            args=(api_key, prompt, count, out_dir, input_images),
            daemon=True,
        ).start()

    def _run_generation(
        self,
        api_key: str,
        prompt: str,
        count: int,
        out_dir: str,
        input_images: list,
    ):
        try:
            client = genai.Client(api_key=api_key)
            if input_images:
                self.after(0, self._log, f"Sending {count} request(s) with {len(input_images)} input image(s)…")
            else:
                self.after(0, self._log, f"Sending {count} request(s) in parallel…")
            with ThreadPoolExecutor(max_workers=count) as executor:
                futures = {
                    executor.submit(self._generate_one, client, prompt, out_dir, input_images): i + 1
                    for i in range(count)
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        filename = future.result()
                        if filename:
                            self.after(0, self._log, f"Image {idx} saved: {filename}")
                            if sys.platform == "darwin":
                                subprocess.run(["open", filename], check=False)
                    except Exception as exc:
                        self.after(0, self._log, f"Image {idx} failed: {exc}")
        except Exception as exc:
            self.after(0, self._log, f"Error: {exc}")
        finally:
            self.after(0, self._finish_generation)

    def _generate_one(
        self,
        client: genai.Client,
        prompt: str,
        out_dir: str,
        input_images: list,
    ) -> str | None:
        contents: list = [prompt, *input_images] if input_images else prompt
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        if not response.candidates or not response.candidates[0].content:
            self.after(0, self._log, "No content returned — request may have been blocked.")
            return None

        for part in response.candidates[0].content.parts:
            if part.text:
                self.after(0, self._log, f"Model: {part.text.strip()}")
            elif part.inline_data:
                image = Image.open(BytesIO(part.inline_data.data))
                ts = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(out_dir, f"{MODEL_NAME}_{ts}_{random.randint(0, 999)}.png")
                image.save(filename)
                return filename

        return None

    def _finish_generation(self):
        self.progress.stop()
        self.gen_btn.config(state="normal")
        self._log("Done.")


if __name__ == "__main__":
    App().mainloop()
