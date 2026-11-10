"""Generate MELZZI's original background tracks (one per line) for reels.

Usage: python3 src/make_music.py   ->  assets/music/{CLEAR,GLOW,CALM,BALANCE}.m4a
Everything is synthesised here from sine/noise oscillators, so the tracks are
original and free of third-party copyright.
"""
import subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

ROOT = Path(__file__).resolve().parent.parent
SR = 44100
LENGTH = 32.0  # seconds; reels are ~25 s, reel.py trims and fades

NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name, octave):
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave + 1) - 69) / 12)


def chord(root, quality, octave=4):
    steps = {"maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "sus2": [0, 2, 7]}[quality]
    base = NOTE[root] + 12 * (octave + 1)
    return [440.0 * 2 ** ((base + s - 69) / 12) for s in steps]


def env(n, a=0.005, d=0.6, sustain=0.0, r=0.05):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * (sustain + (1 - sustain) * np.exp(-t / d))
    rel = int(r * SR)
    if rel and n > rel:
        e[-rel:] *= np.linspace(1, 0, rel)
    return e


def keys(f, dur, bright=1.0):
    """Soft electric-piano: a few decaying partials + light tremolo."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.35 * bright * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.4)
         + 0.12 * bright * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t / 0.2))
    return s * env(n, 0.004, 0.9, 0.08, 0.08) * (1 + 0.08 * np.sin(2 * np.pi * 5 * t))


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det in (-0.004, 0.0, 0.004):
            s += np.sin(2 * np.pi * f * (1 + det) * t) + 0.25 * np.sin(2 * np.pi * 2 * f * (1 + det) * t)
    a = int(0.6 * SR)
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    e[-a:] *= np.linspace(1, 0, a)
    return s * e / (3 * len(freqs))


def bass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)) * env(n, 0.01, 0.5, 0.3, 0.06)


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 70 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12)


def noise_hit(dur, decay, lo, hi, rng):
    n = int(dur * SR)
    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, rng.standard_normal(n)) * np.exp(-np.arange(n) / SR / decay)


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += gain * sig[: j - i]


def reverb(x, mix=0.25):
    out = x.copy()
    for delay, g in ((0.031, 0.5), (0.047, 0.45), (0.071, 0.4), (0.113, 0.35)):
        d = int(delay * SR)
        y = np.zeros_like(x)
        y[d:] = x[:-d]
        for _ in range(3):
            y[d:] += g * y[:-d]
        out += mix * 0.25 * y
    return out


STYLES = {
    # line: key progression (root, quality), bpm, drums, brightness, arpeggio pattern (chord tone indices, 8ths)
    "CLEAR": dict(prog=[("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")], bpm=104, drums="light", bright=1.0,
                  arp=[0, 2, 1, 2, 0, 2, 1, 3]),
    "GLOW": dict(prog=[("D", "maj"), ("B", "min"), ("G", "maj"), ("A", "maj")], bpm=112, drums="pop", bright=1.2,
                 arp=[0, 1, 2, 1, 3, 2, 1, 2]),
    "CALM": dict(prog=[("F", "maj7"), ("D", "min7"), ("A#", "maj7"), ("C", "sus2")], bpm=76, drums="none", bright=0.6,
                 arp=[0, 2, 3, 2, 1, 2, 3, 2]),
    "BALANCE": dict(prog=[("E", "min"), ("C", "maj"), ("G", "maj"), ("D", "maj")], bpm=92, drums="steady", bright=0.9,
                    arp=[0, 1, 2, 3, 2, 1, 0, 1]),
}


def render(line, seed):
    st = STYLES[line]
    rng = np.random.default_rng(seed)
    beat = 60 / st["bpm"]
    bar = 4 * beat
    n = int(LENGTH * SR)
    mus, drm = np.zeros(n), np.zeros(n)
    t, i = 0.0, 0
    while t < LENGTH:
        root, q = st["prog"][i % 4]
        notes = chord(root, q, 4)
        notes = notes + [notes[0] * 2]  # top octave for arps
        mus_pad = pad(chord(root, q, 3), bar + 0.4)
        place(mus, mus_pad, t, 0.35 if line == "CALM" else 0.18)
        place(mus, bass(hz(root, 2), bar * 0.95), t, 0.45)
        for k, idx in enumerate(st["arp"]):
            if line == "CALM" and k % 2:
                continue  # sparser for CALM
            f = notes[idx % len(notes)] * (2 if (i % 8 >= 4 and k == 4) else 1)
            place(mus, keys(f, beat * 1.6, st["bright"]), t + k * beat / 2, 0.3 * (0.85 + 0.3 * rng.random()))
        for b in range(4):
            bt = t + b * beat
            if st["drums"] == "none":
                place(drm, noise_hit(0.12, 0.05, 4000, 9000, rng), bt + beat / 2, 0.05)  # soft shaker
                continue
            if b in (0, 2) or (st["drums"] == "pop" and b == 3 and i % 2):
                place(drm, kick(), bt, 0.9)
            if b in (1, 3):
                place(drm, noise_hit(0.2, 0.06, 1200, 6000, rng), bt, 0.2 if st["drums"] != "light" else 0.13)
            for h in (0, 0.5):
                place(drm, noise_hit(0.04, 0.012, 7000, 13000, rng), bt + h * beat, 0.04)
        t += bar
        i += 1
    mix = reverb(mus, 0.35) + drm * (0.8 if line != "CALM" else 1.0)
    mix -= mix.mean()
    mix /= np.max(np.abs(mix)) + 1e-9
    mix *= 0.89  # about -1 dBFS peak; reel.py sets the final level
    fade = int(1.5 * SR)
    mix[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
    mix[-fade:] *= np.linspace(1, 0, fade)
    # light stereo width: delay right channel a few ms
    right = np.concatenate([np.zeros(int(0.012 * SR)), mix[: -int(0.012 * SR)]])
    return np.stack([mix, 0.85 * right + 0.15 * mix], axis=1)


def main():
    out = ROOT / "assets" / "music"
    out.mkdir(parents=True, exist_ok=True)
    for k, line in enumerate(STYLES):
        wav = out / f"{line}.wav"
        wavfile.write(wav, SR, (render(line, 7 + k) * 32767).astype(np.int16))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "160k",
                        "-ar", "48000", str(out / f"{line}.m4a")], check=True)
        wav.unlink()
        print("music", out / f"{line}.m4a")


if __name__ == "__main__":
    main()
