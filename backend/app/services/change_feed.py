"""In-memory change feed: which kinds of crew data changed, announced on the live stream.

Every successful write through the API (and every background job that writes) records the
affected data domains here. Each open live stream remembers the last sequence it sent and
forwards newer changes as a ``sync`` event, so every cabin display reloads only the screens
whose data actually changed. Nothing here is persisted: a restart simply starts a new feed,
and screens still refresh on their own timers.
"""

from __future__ import annotations

import re
import threading
from collections import deque

DOMAINS = ("vitals", "vision", "sleep", "psych", "auscultation", "alerts", "streaks")

_ROUTES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"^/api/v1/measurements\b"), ("vitals", "vision", "alerts", "streaks")),
    (re.compile(r"^/api/v1/(psych|cognitive)/"), ("psych", "sleep", "alerts", "streaks")),
    (re.compile(r"^/api/v1/sleep/"), ("sleep", "alerts", "streaks")),
    (re.compile(r"^/api/v1/vision/"), ("vision", "alerts")),
    (re.compile(r"^/api/v1/auscultation/"), ("auscultation", "alerts")),
    (re.compile(r"^/api/v1/(alerts|diagnosis)/"), ("alerts",)),
    (re.compile(r"^/api/v1/comms/"), ("alerts",)),
    (re.compile(r"^/api/v1/environment\b"), ("alerts",)),
    (re.compile(r"^/api/v1/crew\b"), ("vitals", "streaks")),
)

_HISTORY = 256
_lock = threading.Lock()
_events: deque[tuple[int, tuple[str, ...]]] = deque(maxlen=_HISTORY)
_sequence = 0


def domains_for_path(path: str) -> tuple[str, ...]:
    """Data domains a successful write on this API path can affect."""
    for pattern, domains in _ROUTES:
        if pattern.search(path):
            return domains
    return ()


def publish(*domains: str) -> int:
    """Record a change; returns the new sequence number (unchanged when nothing applies)."""
    global _sequence
    known = tuple(sorted({d for d in domains if d in DOMAINS}))
    with _lock:
        if known:
            _sequence += 1
            _events.append((_sequence, known))
        return _sequence


def current() -> int:
    """Latest sequence number; a new stream starts from here."""
    with _lock:
        return _sequence


def changes_since(sequence: int) -> tuple[int, list[str]]:
    """Domains changed after ``sequence`` and the sequence to remember next time."""
    with _lock:
        oldest = _events[0][0] if _events else _sequence + 1
        if sequence < oldest - 1:
            # The stream fell too far behind: tell it everything may have changed.
            return _sequence, list(DOMAINS)
        changed = {d for seq, ds in _events if seq > sequence for d in ds}
        return _sequence, sorted(changed)
