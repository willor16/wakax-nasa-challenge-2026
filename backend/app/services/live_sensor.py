"""Live wearable sensor: a continuous Lead II ECG and core temperature for one crew member.

This is the one explicitly simulated signal in SpaceScan. It stands in for the chest strap
and temperature patch during demonstrations, and it always follows the crew member's own
latest real readings (resting heart rate, heart-rate variability, core temperature):

* beats are placed with beat-to-beat (R-R) variability derived from the logged HRV
  (RMSSD is about the square root of 2 times the R-R standard deviation);
* each beat is drawn with the P-QRS-T morphology used for the stored strips
  (``sensor_simulator.ecg_strip``), sampled at 125 Hz for 25 mm/s paper speed;
* core temperature drifts by a few hundredths of a degree around the logged value.

A test tool, or the crew physician, can inject a temporary condition (tachycardia, fever)
through ``POST /api/v1/sensors/simulate``. It is kept in memory only and ends by itself.
"""

from __future__ import annotations

import math
import random
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field

SAMPLE_RATE_HZ = 125
FRAME_SECONDS = 0.25  # 4 frames per second
PAPER_SPEED_MM_S = 25
TEMP_WOBBLE_C = 0.03
REFRESH_SECONDS = 2.0  # how often a stream re-reads the latest real readings

# P, Q, R, S, T waves: (centre in s from the R peak, width in s, amplitude in mV).
WAVES = (
    (-0.20, 0.025, 0.12),
    (-0.03, 0.010, -0.12),
    (0.0, 0.012, 1.25),
    (0.03, 0.010, -0.22),
    (0.26, 0.045, 0.30),
)

DEFAULTS = {"resting_hr_bpm": 64.0, "hrv_rmssd_ms": 55.0, "body_temp_c": 36.8}


@dataclass(frozen=True)
class Override:
    heart_rate_bpm: float | None
    body_temp_c: float | None
    hrv_rmssd_ms: float | None
    label_en: str
    ends_at: float


_overrides: dict[str, Override] = {}
_lock = threading.Lock()


def set_override(
    crew_id: str,
    *,
    heart_rate_bpm: float | None = None,
    body_temp_c: float | None = None,
    hrv_rmssd_ms: float | None = None,
    duration_s: float = 120.0,
    label_en: str = "Injected sensor condition",
) -> Override:
    """Inject a temporary sensor condition for one crew member (memory only)."""
    override = Override(
        heart_rate_bpm, body_temp_c, hrv_rmssd_ms, label_en, time.monotonic() + duration_s
    )
    with _lock:
        _overrides[crew_id] = override
    return override


def clear_override(crew_id: str) -> None:
    with _lock:
        _overrides.pop(crew_id, None)


def active_override(crew_id: str) -> Override | None:
    with _lock:
        override = _overrides.get(crew_id)
        if override and override.ends_at <= time.monotonic():
            _overrides.pop(crew_id, None)
            return None
        return override


def latest_readings(conn: sqlite3.Connection, crew_id: str) -> dict[str, float]:
    """Latest real heart rate, HRV and core temperature (any source), with safe defaults."""
    found = dict(DEFAULTS)
    for key in DEFAULTS:
        row = conn.execute(
            """SELECT value_num FROM measurements WHERE crew_id = ? AND metric_key = ?
               AND value_num IS NOT NULL ORDER BY recorded_at_utc DESC, id DESC LIMIT 1""",
            (crew_id, key),
        ).fetchone()
        if row:
            found[key] = float(row["value_num"])
    return found


def sensor_inputs(conn: sqlite3.Connection, crew_id: str) -> tuple[dict[str, float], str | None]:
    """What the sensor should show now: real readings, replaced by an injected condition."""
    values = latest_readings(conn, crew_id)
    override = active_override(crew_id)
    if override is None:
        return values, None
    if override.heart_rate_bpm is not None:
        values["resting_hr_bpm"] = override.heart_rate_bpm
    if override.hrv_rmssd_ms is not None:
        values["hrv_rmssd_ms"] = override.hrv_rmssd_ms
    if override.body_temp_c is not None:
        values["body_temp_c"] = override.body_temp_c
    return values, override.label_en


def rhythm_text(heart_rate_bpm: float) -> str:
    if heart_rate_bpm > 100:
        return "Sinus Tachycardia"
    if heart_rate_bpm < 50:
        return "Sinus Bradycardia"
    return "Normal Sinus"


@dataclass
class LiveEcg:
    """Continuous generator: call ``frame()`` every 250 ms for the next block of samples."""

    heart_rate_bpm: float = DEFAULTS["resting_hr_bpm"]
    hrv_rmssd_ms: float = DEFAULTS["hrv_rmssd_ms"]
    body_temp_c: float = DEFAULTS["body_temp_c"]
    seed: int = 0
    _rng: random.Random = field(init=False, repr=False)
    _t: float = field(init=False, default=0.0)  # seconds of signal produced so far
    _beats: deque = field(init=False, repr=False)  # R-peak times (s)
    _rr: deque = field(init=False, repr=False)  # recent R-R intervals (s)
    _temp_phase: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._beats = deque([0.35])
        self._rr = deque(maxlen=16)
        self._temp_phase = self._rng.uniform(0, 2 * math.pi)

    def update(self, heart_rate_bpm: float, hrv_rmssd_ms: float, body_temp_c: float) -> None:
        target = min(220.0, max(30.0, heart_rate_bpm))
        if abs(target - self.heart_rate_bpm) > 5:
            # A new rate (a fresh reading or an injected condition) takes over from the next
            # beat instead of after the beats already queued at the old rate.
            while len(self._beats) > 1 and self._beats[-1] > self._t:
                self._beats.pop()
            self._rr.clear()
        self.heart_rate_bpm = target
        self.hrv_rmssd_ms = min(200.0, max(2.0, hrv_rmssd_ms))
        self.body_temp_c = body_temp_c

    def _extend_beats(self, until: float) -> None:
        mean_rr = 60.0 / self.heart_rate_bpm
        sd_rr = self.hrv_rmssd_ms / 1000.0 / math.sqrt(2)
        while self._beats[-1] < until + 0.6:
            rr = max(0.27, self._rng.gauss(mean_rr, sd_rr))
            self._rr.append(rr)
            self._beats.append(self._beats[-1] + rr)
        while len(self._beats) > 2 and self._beats[1] < self._t - 0.6:
            self._beats.popleft()

    def _value(self, now: float) -> float:
        value = 0.0
        for peak in self._beats:
            offset = now - peak
            if -0.4 < offset < 0.5:
                for centre, width, amp in WAVES:
                    value += amp * math.exp(-((offset - centre) ** 2) / (2 * width**2))
        return value + self._rng.gauss(0, 0.01)

    def frame(self) -> dict:
        count = round(SAMPLE_RATE_HZ * FRAME_SECONDS)
        start = self._t
        self._extend_beats(start + FRAME_SECONDS)
        samples = [round(self._value(start + i / SAMPLE_RATE_HZ), 3) for i in range(count)]
        self._t = start + count / SAMPLE_RATE_HZ
        self._temp_phase += 0.02
        recent = list(self._rr)[-3:]
        live_hr = 60.0 / (sum(recent) / len(recent)) if recent else self.heart_rate_bpm
        # Displayed HRV follows the logged value with the small spread a wearable shows;
        # the beat timing itself already carries that variability.
        rmssd = max(2.0, self.hrv_rmssd_ms + self._rng.gauss(0, 1.5))
        return {
            "t0_s": round(start, 3),
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "paper_speed_mm_s": PAPER_SPEED_MM_S,
            "lead": "II",
            "samples": samples,
            "heart_rate_bpm": round(live_hr),
            "hrv_ms": round(rmssd),
            "body_temp_c": round(
                self.body_temp_c + TEMP_WOBBLE_C * math.sin(self._temp_phase), 2
            ),
            "rhythm_text": rhythm_text(live_hr),
        }
