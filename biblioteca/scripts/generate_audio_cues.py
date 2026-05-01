"""Generate TTS audio cues for cat / wrench / house.

Run from the project root:
    python scripts/generate_audio_cues.py

By default uses gTTS (Google Text-to-Speech). Internet required on first
run. If gTTS is not installed and you're on macOS, falls back to the
built-in `say` command + `afconvert`.

Outputs:
    assets/audio/cat.mp3
    assets/audio/wrench.mp3
    assets/audio/house.mp3
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "audio"
WORDS = ["cat", "wrench", "house"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Try gTTS first (cross-platform, consistent voice across machines)
    try:
        from gtts import gTTS  # noqa: F401
        return generate_with_gtts()
    except ImportError:
        pass

    # macOS fallback: `say` → AIFF → afconvert → WAV (frontend uses .mp3
    # extension by default; rename or update config.js if you go this route)
    if sys.platform == "darwin" and shutil.which("say") and shutil.which("afconvert"):
        print("gTTS not installed; falling back to macOS `say` + afconvert (writes .wav).")
        print("To use gTTS instead: pip install gTTS")
        return generate_with_say()

    print(
        "ERROR: neither gTTS nor macOS `say` is available.\n"
        "  Install gTTS (recommended for reproducibility):\n"
        "    pip install gTTS\n"
        "  Then re-run: python scripts/generate_audio_cues.py"
    )
    return 1


def generate_with_gtts() -> int:
    from gtts import gTTS
    for word in WORDS:
        out = OUT_DIR / f"{word}.mp3"
        print(f"  gTTS → {out.relative_to(ROOT)}")
        gTTS(text=word, lang="en", slow=False).save(str(out))
    print(f"\nDone. {len(WORDS)} mp3 files in {OUT_DIR}")
    return 0


def generate_with_say() -> int:
    voice = "Samantha"  # adjust to taste; consistent within one machine
    for word in WORDS:
        aiff = OUT_DIR / f"{word}.aiff"
        wav = OUT_DIR / f"{word}.wav"
        print(f"  say → {wav.relative_to(ROOT)}")
        subprocess.run(["say", "-v", voice, "-o", str(aiff), word], check=True)
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@44100", str(aiff), str(wav)],
            check=True,
        )
        os.remove(aiff)
    print(
        f"\nDone. {len(WORDS)} wav files in {OUT_DIR}\n"
        "NOTE: frontend/config.js defaults to .mp3 — either rename to .mp3 "
        "or update ASSETS.audioPath in config.js to use .wav."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())