#!/usr/bin/env python3
"""Read lines aloud in one of BioManager's own voices, with Qwen3-TTS.

    <tts python> scripts/qwen-voice.py jobs.json

jobs.json is a list of {"voice": "zh-a", "text": "…", "out": "/path/line.wav"}.
The voices are promo/voices/<name>.wav, a short clip made once with
Qwen3-TTS VoiceDesign from the description in promo/voices/voices.json;
every line is read by Qwen3-TTS Base copying that clip, so the narrator is
the same in every video. Lines whose file already exists are skipped.

It runs in its own environment, not the app's: MLX on Apple silicon.
    python3.12 -m venv ~/.cache/biomanager-tts/venv
    ~/.cache/biomanager-tts/venv/bin/pip install mlx-audio soundfile
scripts/explainer-video.py and daily-video.py call it (BIOMANAGER_TTS_PYTHON
names another interpreter). Qwen3-TTS is Apache 2.0; the model, about
2.7 GB, is downloaded from Hugging Face the first time.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from mlx_audio.tts.utils import load_model

ROOT = Path(__file__).resolve().parent.parent
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit"


def main():
    jobs = [j for j in json.loads(Path(sys.argv[1]).read_text()) if not Path(j["out"]).exists()]
    if not jobs:
        return
    voices = json.loads((ROOT / "promo/voices/voices.json").read_text())
    t = time.time()
    model = load_model(MODEL)
    print(f"qwen-voice: model ready in {time.time() - t:.0f} s; {len(jobs)} lines", flush=True)
    for n, job in enumerate(jobs, 1):
        v = voices[job["voice"]]
        parts = model.generate(text=job["text"], ref_audio=str(ROOT / "promo/voices" / f"{job['voice']}.wav"),
                               ref_text=v["text"], lang_code=v["language"])
        audio = np.concatenate([np.array(p.audio) for p in parts])
        out = Path(job["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(f"{out}.part.wav", audio, model.sample_rate)
        os.replace(f"{out}.part.wav", out)
        print(f"qwen-voice: {n}/{len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
