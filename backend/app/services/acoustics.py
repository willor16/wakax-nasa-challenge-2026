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
import json
import time
import wave
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ENVELOPE_POINTS = 600  # points kept for the waveform chart (30 s -> 20 points per second)

# Log-mel spectrogram fed to the sound classifier: one window is CHANNELS x FRAMES.
# The heart band covers S1/S2, gallops and most murmurs; the lung band covers breath
# sounds, wheezes and crackles. A lung window is longer so it always holds a full breath.
FEATURE_BANDS = 24
# The mel bands plus one impulsiveness channel (crest factor per frame), which makes
# short explosive sounds such as crackles stand out.
FEATURE_CHANNELS = FEATURE_BANDS + 1
FEATURE_FRAMES = 64
FFT_SIZE = 512
FEATURE_CONFIG = {
    "CARDIAC": {"window_s": 4.0, "fmin": 20.0, "fmax": 800.0},
    "PULMONARY": {"window_s": 8.0, "fmin": 80.0, "fmax": 1800.0},
}
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
CLASSIFIER_META = MODELS_DIR / "auscultation_cnn_meta.json"

CLASS_LABELS = {
    "normal_s1_s2": "Normal S1/S2",
    "systolic_murmur_suspected": "Suspected systolic murmur",
    "extra_gallop_sound": "Suspected extra (gallop) sound",
    "irregular_rhythm": "Irregular rhythm",
    "low_signal_noise": "Too noisy to judge",
    "normal_vesicular": "Normal breath sounds",
    "wheeze_suspected": "Suspected wheeze",
    "crackle_suspected": "Suspected crackles",
    "diminished_breath_sounds": "Diminished breath sounds",
}
# Sound classes that are sent to the crew physician for a listening review.
REVIEW_CLASSES = frozenset({
    "systolic_murmur_suspected", "extra_gallop_sound", "irregular_rhythm",
    "wheeze_suspected", "crackle_suspected", "diminished_breath_sounds",
})


def _mel(hz: np.ndarray) -> np.ndarray:
    return 2595.0 * np.log10(1.0 + hz / 700.0)


@lru_cache(maxsize=8)
def _mel_filters(sample_rate: int, fmin: float, fmax: float) -> np.ndarray:
    """Triangular mel filter bank, BANDS x (FFT_SIZE // 2 + 1)."""
    edges_mel = np.linspace(_mel(np.array(fmin)), _mel(np.array(fmax)), FEATURE_BANDS + 2)
    edges = 700.0 * (10 ** (edges_mel / 2595.0) - 1.0)
    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / sample_rate)
    bank = np.zeros((FEATURE_BANDS, freqs.size))
    for b in range(FEATURE_BANDS):
        lo, mid, hi = edges[b], edges[b + 1], edges[b + 2]
        rising = (freqs - lo) / max(mid - lo, 1e-9)
        falling = (hi - freqs) / max(hi - mid, 1e-9)
        bank[b] = np.clip(np.minimum(rising, falling), 0, None)
    return bank


def log_mel(window: np.ndarray, sample_rate: int, organ_type: str) -> np.ndarray:
    """Features of one window: CHANNELS x FRAMES (log-mel bands plus crest factor).

    Only the mean is removed (not the spread), so a weak breath over the noise floor keeps
    its small modulation depth, which is what separates diminished from normal sounds.
    """
    cfg = FEATURE_CONFIG[organ_type]
    hop = max(1, len(window) // FEATURE_FRAMES)
    padded = np.pad(window, (0, FFT_SIZE))
    raw = np.stack([padded[i * hop: i * hop + FFT_SIZE] for i in range(FEATURE_FRAMES)])
    power = np.abs(np.fft.rfft(raw * np.hanning(FFT_SIZE), axis=1)) ** 2
    bands = power @ _mel_filters(sample_rate, cfg["fmin"], cfg["fmax"]).T
    feats = np.log10(bands + 1e-6).T
    feats = feats - feats.mean()
    crest = np.log10((np.abs(raw).max(axis=1) ** 2 + 1e-9) / (np.mean(raw**2, axis=1) + 1e-9))
    return np.vstack([feats, (crest - crest.mean())[None, :]]).astype(np.float32)


def feature_windows(samples: np.ndarray, sample_rate: int, organ_type: str) -> np.ndarray:
    """Overlapping windows of a recording (half-window hop), stacked: N x CHANNELS x FRAMES."""
    samples = samples.astype(np.float64)
    peak = np.max(np.abs(samples)) or 1.0
    samples = samples / peak
    size = int(FEATURE_CONFIG[organ_type]["window_s"] * sample_rate)
    if len(samples) < size:
        samples = np.pad(samples, (0, size - len(samples)))
    starts = range(0, len(samples) - size + 1, size // 2)
    return np.stack([log_mel(samples[s:s + size], sample_rate, organ_type) for s in starts])


@lru_cache(maxsize=1)
def _classifier() -> dict | None:
    """Sound classifier sessions (one per organ), or None when the model is not installed."""
    if not CLASSIFIER_META.exists():
        return None
    import onnxruntime as ort

    meta = json.loads(CLASSIFIER_META.read_text(encoding="utf-8"))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    sessions = {
        organ: ort.InferenceSession(str(MODELS_DIR / info["file"]), options,
                                    providers=["CPUExecutionProvider"])
        for organ, info in meta["organs"].items()
    }
    return {"meta": meta, "sessions": sessions}


def classify(samples: np.ndarray, sample_rate: int, organ_type: str) -> dict | None:
    """Most likely sound class over the whole recording (window probabilities averaged)."""
    model = _classifier()
    if model is None or samples.size == 0:
        return None
    started = time.perf_counter()
    windows = feature_windows(samples, sample_rate, organ_type)
    session = model["sessions"][organ_type]
    probs = session.run(None, {session.get_inputs()[0].name: windows})[0].mean(axis=0)
    classes = model["meta"]["organs"][organ_type]["classes"]
    best = int(np.argmax(probs))
    return {
        "class_key": classes[best],
        "class_label_en": CLASS_LABELS[classes[best]],
        "confidence_pct": round(float(probs[best]) * 100, 1),
        "probabilities": {c: round(float(p) * 100, 1) for c, p in zip(classes, probs, strict=True)},
        "needs_review": classes[best] in REVIEW_CLASSES,
        "inference_ms": round((time.perf_counter() - started) * 1000, 1),
        "windows": int(len(windows)),
        "model_version": model["meta"]["version"],
    }


def _peak_times(env: np.ndarray, rate_hz: float, min_gap_s: float) -> list[int]:
    """Indices of envelope peaks above 35% of the maximum, at least ``min_gap_s`` apart."""
    threshold = 0.35 * (env.max() or 1.0)
    gap = max(1, int(min_gap_s * rate_hz))
    peaks: list[int] = []
    for i in range(1, len(env) - 1):
        if env[i] >= threshold and env[i] >= env[i - 1] and env[i] > env[i + 1]:
            if peaks and i - peaks[-1] < gap:
                if env[i] > env[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    return peaks


def heart_sound_balance(samples: np.ndarray, sample_rate: int) -> float | None:
    """S1/S2 energy ratio: louder heart sound of each pair over the softer one."""
    peak = np.max(np.abs(samples)) or 1.0
    env = _envelope(samples / peak, sample_rate, 0.02)[:: sample_rate // 100]
    peaks = _peak_times(env, 100.0, 0.18)
    if len(peaks) < 4:
        return None
    heights = env[peaks]
    pairs = [(heights[i], heights[i + 1]) for i in range(0, len(heights) - 1, 2)]
    ratios = [max(a, b) / max(min(a, b), 1e-6) for a, b in pairs]
    return round(float(np.median(ratios)), 2)


def breath_phase_ratio(samples: np.ndarray, sample_rate: int) -> float | None:
    """Inspiration / expiration energy: loud (inspiratory) half of each breath over the rest."""
    peak = np.max(np.abs(samples)) or 1.0
    env = _envelope(samples / peak, sample_rate, 0.25)[:: sample_rate // 50]
    if env.max() <= 0:
        return None
    loud = env >= np.percentile(env, 60)
    quiet = ~loud
    if not quiet.any():
        return None
    return round(float(env[loud].mean() / max(env[quiet].mean(), 1e-6)), 2)


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
    """Demo normal (vesicular) breath sound: 100-1000 Hz breath noise, louder and shorter
    in inspiration than in expiration, over a faint cabin noise floor."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate

    def band(low: float, high: float) -> np.ndarray:
        spectrum = np.fft.rfft(rng.normal(0, 1, n))
        freqs = np.fft.rfftfreq(n, 1 / sample_rate)
        spectrum[(freqs < low) | (freqs > high)] = 0
        noise = np.fft.irfft(spectrum, n)
        return noise / (noise.std() or 1.0)

    phase = (t * rpm / 60.0) % 1.0
    inspiration = 0.4
    shape = np.where(
        phase < inspiration,
        np.sin(np.pi * phase / inspiration),
        0.45 * np.sin(np.pi * (phase - inspiration) / (1 - inspiration)),
    )
    return 0.8 * band(100, 1000) * shape + 0.02 * band(30, 1800)
