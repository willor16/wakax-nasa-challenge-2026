"""Signal analysis for 30-second heart and lung recordings.

The same steps run in the browser right after a recording (see
``frontend/app/utils/acoustics.ts``) and here for WAV files:

1. Envelope: absolute signal, smoothed with a moving average.
2. Rate: the strongest repeat of the envelope (autocorrelation) inside the
   physiological window - 40-180 per minute for the heart, 6-40 for breathing.
3. Rhythm regularity: how sharp that repeat is (autocorrelation peak height).
4. Signal quality: contrast between the loud sounds and the quiet floor.

These are screening numbers for the crew physician, not a diagnosis: murmurs
and added lung sounds are left to the physician's listening review.
"""

from __future__ import annotations

import io
import wave
from dataclasses import asdict, dataclass

import numpy as np

ENVELOPE_POINTS = 600  # points kept for the waveform chart (30 s -> 20 points per second)


@dataclass(slots=True)
class AcousticFindings:
    organ_type: str
    rate_per_min: float | None
    regularity_pct: float
    signal_quality_pct: float
    rhythm_label: str
    envelope: list[float]

    def to_dict(self) -> dict:
        return asdict(self)


def _envelope(samples: np.ndarray, sample_rate: int, window_s: float) -> np.ndarray:
    window = max(1, int(sample_rate * window_s))
    kernel = np.ones(window) / window
    return np.convolve(np.abs(samples), kernel, mode="same")


def _dominant_rate(
    env: np.ndarray, rate_hz: float, low_bpm: float, high_bpm: float
) -> tuple[float | None, float]:
    centred = env - env.mean()
    if not np.any(centred):
        return None, 0.0
    corr = np.correlate(centred, centred, mode="full")[len(centred) - 1 :]
    corr = corr / corr[0]
    min_lag = int(rate_hz * 60.0 / high_bpm)
    max_lag = min(len(corr) - 1, int(rate_hz * 60.0 / low_bpm))
    if max_lag <= min_lag:
        return None, 0.0
    segment = corr[min_lag:max_lag]
    best = int(np.argmax(segment)) + min_lag
    # Prefer the fundamental: a peak at half the lag that is nearly as strong wins.
    half = best // 2
    if half >= min_lag and corr[half] > 0.8 * corr[best]:
        best = half
    peak = float(corr[best])
    if peak <= 0.1:
        return None, max(0.0, peak)
    return 60.0 * rate_hz / best, peak


def analyse(samples: np.ndarray, sample_rate: int, organ_type: str) -> AcousticFindings:
    """Screening numbers for one recording (``organ_type`` CARDIAC or PULMONARY)."""
    samples = samples.astype(np.float64)
    if samples.size == 0:
        return AcousticFindings(organ_type, None, 0.0, 0.0, "No signal", [])
    peak = np.max(np.abs(samples)) or 1.0
    samples = samples / peak

    cardiac = organ_type == "CARDIAC"
    env = _envelope(samples, sample_rate, 0.02 if cardiac else 0.25)
    step = max(1, sample_rate // 50)  # 50 Hz envelope for the rate search
    env_ds = env[::step]
    rate_hz = sample_rate / step
    low, high = (40.0, 180.0) if cardiac else (6.0, 40.0)
    rate, sharpness = _dominant_rate(env_ds, rate_hz, low, high)

    floor = float(np.percentile(env, 20))
    top = float(np.percentile(env, 95)) or 1.0
    quality = round(float(np.clip((1.0 - floor / top) * 100.0, 0.0, 99.0)), 1)
    regularity = round(float(np.clip(sharpness, 0, 1)) * 100, 1)
    if rate is None:
        label = "Unclear signal - record again"
    elif cardiac:
        label = (
            "Regular S1/S2 rhythm" if regularity >= 45 else "Irregular rhythm - physician review"
        )
    else:
        label = (
            "Steady breathing pattern"
            if regularity >= 35
            else "Uneven breathing - physician review"
        )

    chart = np.interp(np.linspace(0, len(env) - 1, ENVELOPE_POINTS), np.arange(len(env)), env)
    chart = chart / (chart.max() or 1.0)
    return AcousticFindings(
        organ_type=organ_type,
        rate_per_min=round(rate, 1) if rate else None,
        regularity_pct=regularity,
        signal_quality_pct=quality,
        rhythm_label=label,
        envelope=[round(float(v), 3) for v in chart],
    )


def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as handle:
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
        channels = handle.getnchannels()
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
    samples = np.frombuffer(frames, dtype=dtype).astype(np.float64)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def write_wav(samples: np.ndarray, sample_rate: int) -> bytes:
    scaled = np.clip(samples / (np.max(np.abs(samples)) or 1.0), -1, 1)
    pcm = (scaled * 30000).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def simulate_heart(bpm: float, seconds: float, sample_rate: int, seed: int) -> np.ndarray:
    """Training/demo phonocardiogram: S1 and S2 bursts with small beat-to-beat variation."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    signal = rng.normal(0, 0.02, n)
    beat = 60.0 / bpm
    onset = 0.1
    while onset < seconds:
        for delay, freq, amp, dur in ((0.0, 55, 1.0, 0.11), (0.30 * beat, 75, 0.7, 0.08)):
            start = onset + delay
            mask = (t >= start) & (t < start + dur)
            local = t[mask] - start
            signal[mask] += amp * np.sin(2 * np.pi * freq * local) * np.hanning(mask.sum())
        onset += beat * (1 + rng.normal(0, 0.02))
    return signal


def simulate_lungs(rpm: float, seconds: float, sample_rate: int, seed: int) -> np.ndarray:
    """Training/demo breath sound: filtered noise shaped by the breathing cycle."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    noise = np.convolve(rng.normal(0, 1, n), np.ones(8) / 8, mode="same")
    cycle = np.clip(np.sin(2 * np.pi * (rpm / 60.0) * t), 0, None) ** 1.5
    return noise * (0.08 + cycle) + rng.normal(0, 0.01, n)
