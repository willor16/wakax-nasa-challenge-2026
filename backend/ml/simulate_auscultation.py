"""Reproducible simulated heart and lung sounds for the onboard sound classifier (M5).

These are demonstration sounds, not patient recordings: they reproduce the acoustic
signature that defines each class so a small network can learn to separate them. The
app always labels its result as "suspected" and sends any non-normal sound to the crew
physician for a listening review.

Heart (4 kHz, phonocardiogram-like):
* ``normal_s1_s2``: S1 (low, longer) and S2 (higher, shorter) at 50-110 beats/min.
* ``systolic_murmur_suspected``: band-limited noise (150-400 Hz) filling systole,
  diamond shaped (Leatham, Br Heart J 20:399, 1958).
* ``extra_gallop_sound``: a soft, very low third sound 120-180 ms after S2 (S3 gallop).
* ``irregular_rhythm``: beat-to-beat intervals varying widely (irregularly irregular,
  as in atrial fibrillation).
* ``low_signal_noise``: heart sounds buried in cabin and contact noise.

Lungs:
* ``normal_vesicular``: breath noise (100-1000 Hz), louder and longer in inspiration.
* ``wheeze_suspected``: sustained musical tones (300-900 Hz, > 100 ms) in expiration
  (Pasterkamp et al., Am J Respir Crit Care Med 156:974, 1997).
* ``crackle_suspected``: short explosive transients (< 20 ms) in inspiration.
* ``diminished_breath_sounds``: breath much weaker than the noise floor.
* ``low_signal_noise``: no usable breath sound.
"""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 4000

CARDIAC_CLASSES = (
    "normal_s1_s2",
    "systolic_murmur_suspected",
    "extra_gallop_sound",
    "irregular_rhythm",
    "low_signal_noise",
)
PULMONARY_CLASSES = (
    "normal_vesicular",
    "wheeze_suspected",
    "crackle_suspected",
    "diminished_breath_sounds",
    "low_signal_noise",
)


def band_noise(
    rng: np.random.Generator, n: int, low: float, high: float, rate: int = SAMPLE_RATE
) -> np.ndarray:
    """White noise limited to [low, high] Hz, unit standard deviation."""
    spectrum = np.fft.rfft(rng.normal(0, 1, n))
    freqs = np.fft.rfftfreq(n, 1 / rate)
    spectrum[(freqs < low) | (freqs > high)] = 0
    noise = np.fft.irfft(spectrum, n)
    return noise / (noise.std() or 1.0)


def _burst(
    signal: np.ndarray,
    start: float,
    duration: float,
    freq: float,
    amp: float,
    rate: int = SAMPLE_RATE,
) -> None:
    i0 = int(start * rate)
    i1 = min(len(signal), i0 + int(duration * rate))
    if i0 >= len(signal) or i1 <= i0:
        return
    t = np.arange(i1 - i0) / rate
    signal[i0:i1] += amp * np.sin(2 * np.pi * freq * t) * np.hanning(i1 - i0)


def heart_sound(
    kind: str, seconds: float, rng: np.random.Generator, rate: int = SAMPLE_RATE
) -> np.ndarray:
    n = int(seconds * rate)
    signal = np.zeros(n)
    bpm = rng.uniform(50, 110)
    beat = 60.0 / bpm
    weak = kind == "low_signal_noise"
    amp = rng.uniform(0.04, 0.12) if weak else rng.uniform(0.7, 1.2)
    onset = rng.uniform(0.0, beat)
    while onset < seconds:
        systole = (0.30 + rng.normal(0, 0.01)) * beat
        _burst(signal, onset, rng.uniform(0.09, 0.13), rng.uniform(40, 60), amp)
        _burst(signal, onset + systole, rng.uniform(0.06, 0.09), rng.uniform(65, 90), amp * 0.7)
        if kind == "systolic_murmur_suspected":
            i0 = int((onset + 0.11) * rate)
            i1 = min(n, int((onset + systole - 0.01) * rate))
            if i1 > i0:
                shape = np.interp(np.arange(i1 - i0), [0, (i1 - i0) / 2, i1 - i0], [0, 1, 0])
                signal[i0:i1] += (
                    amp * rng.uniform(0.25, 0.5) * shape * band_noise(rng, i1 - i0, 150, 400, rate)
                )
        if kind == "extra_gallop_sound":
            _burst(
                signal,
                onset + systole + rng.uniform(0.12, 0.18),
                0.07,
                rng.uniform(25, 40),
                amp * rng.uniform(0.35, 0.6),
            )
        if kind == "irregular_rhythm":
            onset += beat * rng.uniform(0.55, 1.6)
        else:
            onset += beat * (1 + rng.normal(0, 0.02))
    noise_level = rng.uniform(0.15, 0.4) if weak else rng.uniform(0.005, 0.05)
    signal += noise_level * band_noise(rng, n, 30, 1500, rate)
    return signal


def lung_sound(
    kind: str, seconds: float, rng: np.random.Generator, rate: int = SAMPLE_RATE
) -> np.ndarray:
    n = int(seconds * rate)
    t = np.arange(n) / rate
    rpm = rng.uniform(10, 22)
    cycle = 60.0 / rpm
    phase = ((t + rng.uniform(0, cycle)) % cycle) / cycle
    inspiration = 0.4
    # Inspiration is louder and shorter than expiration.
    shape = np.where(
        phase < inspiration,
        np.sin(np.pi * phase / inspiration),
        0.45 * np.sin(np.pi * (phase - inspiration) / (1 - inspiration)),
    )
    breath = band_noise(rng, n, 100, 1000, rate) * shape
    gain = {"diminished_breath_sounds": rng.uniform(0.06, 0.15), "low_signal_noise": 0.0}.get(
        kind, rng.uniform(0.6, 1.0)
    )
    signal = gain * breath
    expiring = phase >= inspiration
    if kind == "wheeze_suspected":
        f0 = rng.uniform(300, 900)
        glide = f0 * (1 + 0.15 * np.sin(2 * np.pi * phase))
        tone = np.sin(2 * np.pi * np.cumsum(glide) / rate)
        signal += rng.uniform(0.3, 0.6) * tone * expiring * np.clip(shape * 3, 0, 1)
    if kind == "crackle_suspected":
        breaths = int(seconds / cycle) + 2
        for b in range(breaths):
            start = b * cycle - rng.uniform(0, cycle)
            for _ in range(rng.integers(6, 16)):
                at = start + rng.uniform(0.05, inspiration * cycle)
                if 0 <= at < seconds - 0.02:
                    i0 = int(at * rate)
                    k = np.arange(int(rng.uniform(0.004, 0.012) * rate))
                    decay = np.exp(-k / (0.002 * rate))
                    signal[i0 : i0 + len(k)] += (
                        rng.uniform(0.6, 1.2)
                        * decay
                        * np.sin(2 * np.pi * rng.uniform(300, 800) * k / rate)
                    )
    noise_level = (
        rng.uniform(0.05, 0.15)
        if kind in {"low_signal_noise", "diminished_breath_sounds"}
        else rng.uniform(0.005, 0.04)
    )
    signal += noise_level * band_noise(rng, n, 30, 1800, rate)
    return signal


def generate(organ: str, kind: str, seconds: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (heart_sound if organ == "CARDIAC" else lung_sound)(kind, seconds, rng)
