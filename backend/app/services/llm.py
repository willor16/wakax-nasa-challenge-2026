"""Local language model guidance for anomaly findings (D3-05).

The onboard assistant writes a short plain-English summary and three preventive
steps grounded in the medical guide. It runs on the local model server only
(no network beyond this machine). Every answer is checked; anything malformed,
off-topic or slow is replaced by a deterministic answer built from the care
steps and guide protocols already validated for the app. A physician must
review every finding before the crew acts on it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.config import BACKEND_DIR
from app.services.alert_engine import CARE_STEPS


def _local_url(url: str) -> str:
    """The assistant only ever runs on this machine: any other address is ignored."""
    host = (urlparse(url).hostname or "").lower()
    return url if host in ("127.0.0.1", "localhost", "::1") else "http://127.0.0.1:11434"


LLM_URL = _local_url(os.environ.get("SPACESCAN_LLM_URL", "http://127.0.0.1:11434"))
# Open-weight model run by the local model server. The large model writes the clearest
# guidance; on smaller hardware set SPACESCAN_LLM_MODEL=llama3.2:3b (about 2 GB).
LLM_MODEL = os.environ.get("SPACESCAN_LLM_MODEL", "gpt-oss:120b")
# The first answer also loads the model into memory, which can take about half a minute.
LLM_TIMEOUT_SEC = float(os.environ.get("SPACESCAN_LLM_TIMEOUT", "90"))

# Words that must never reach the screen: restricted names (listed in the data
# file ``db/seed_snapshots/screen_word_filter.json``, never in code) and
# internal technology names.
_FILTER_PATH = BACKEND_DIR / "db" / "seed_snapshots" / "screen_word_filter.json"
_RESTRICTED = [bytes.fromhex(v).decode() for v in json.loads(_FILTER_PATH.read_text())["hex"]]
_BLOCKED = re.compile(
    r"\b(" + "|".join(_RESTRICTED) + r"|sqlite|json|fhir|hl7|kiwix|zim|fts5|wal|offline"
    r"|break-glass|dtn|osdr|donki|onnx|ollama|nuxt|python|neural|autoencoder|llm|cnn|ai model"
    r"|language model)\b",
    re.IGNORECASE,
)
MAX_TITLE = 60
MAX_DETAIL = 220
MAX_SUMMARY = 400

SYSTEM_PROMPT = (
    "You assist the physician of a spaceflight crew. Write in plain, calm English for "
    "astronauts, without technology names or code words. Every step must restate one of the "
    "protocol steps provided, keeping its meaning; never add an action that is not listed "
    "and never suggest switching off air, fans or life support. "
    "Answer with JSON only: {\"summary\": string (max 2 sentences), \"steps\": "
    "[{\"title\": string (max 8 words), \"detail\": string (1 sentence)}] with exactly 3 "
    "steps, \"cited_article_ids\": [ids from the protocols list]}. Do not diagnose disease; "
    "suggest preventive actions and when to call the physician."
)


@dataclass
class Guidance:
    summary_en: str
    steps: list[dict[str, str]]
    cited_article_ids: list[str]
    source: str  # "assistant" or "fallback"
    model: str
    issues: list[str] = field(default_factory=list)


# Typographic marks some models use, written the plain way so the text stays simple English.
_PLAIN_MARKS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
    "\u2011": "-", "\u2010": "-", "\u2212": "-", "\u2026": "...", "\u00a0": " ", "\u202f": " ",
    "\u2009": " ", "\u2265": ">=", "\u2264": "<=", "\u00b7": "-", "\u2022": "-", "\u00d7": "x",
    # Subscript and superscript digits (CO2, SpO2, m2) written as plain digits.
    **{chr(0x2080 + d): str(d) for d in range(10)},
    "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
    **{chr(0x2074 + d - 4): str(d) for d in range(4, 10)},
})


def _clean(text: object, limit: int) -> str:
    plain = str(text or "").translate(_PLAIN_MARKS)
    return re.sub(r"\s+", " ", plain).strip()[:limit]


def build_prompt(finding: dict, articles: list[dict]) -> str:
    metrics = "; ".join(
        f"{m['display_name_en']}: {m['value']:g} {m['unit']} (usual {m['baseline']:g} "
        f"{m['unit']}, {m['z']:+.1f} spreads from usual)"
        for m in finding["top_metrics"]
    ) or "no single reading stands out"
    protocols = "\n".join(
        f"- id={a['id']} | {a['title_en']} | steps: "
        + " / ".join(f"{s['title_en']}: {s['detail_en']}" if s.get("detail_en") else s["title_en"]
                     for s in a["steps"])
        + f" | call the physician when: {a['escalation_en']}"
        for a in articles
    )
    return (
        f"Pattern found today: {finding['pattern_label_en']}.\n"
        f"Readings that stand out: {metrics}.\n"
        f"Protocols you may cite:\n{protocols}\n"
        "Choose the 3 listed steps that fit these readings best and restate them simply. "
        "Write the JSON answer now."
    )


def validate(answer: dict, allowed_ids: set[str], default_id: str | None = None
             ) -> tuple[Guidance | None, list[str]]:
    """Check a raw model answer; return cleaned guidance or the reasons it failed.

    Small local models often leave out the citation list. The answer was grounded only
    on the protocols provided, so a missing list is credited to the main protocol
    (``default_id``); a list that names protocols that were not provided is rejected.
    """
    issues: list[str] = []
    if not isinstance(answer, dict):
        return None, ["answer is not an object"]
    summary = _clean(answer.get("summary"), MAX_SUMMARY)
    raw_steps = answer.get("steps")
    steps: list[dict[str, str]] = []
    if not isinstance(raw_steps, list) or len(raw_steps) < 3:
        issues.append("needs 3 steps")
    else:
        for step in raw_steps[:3]:  # small models sometimes add a fourth; keep the first 3
            if not isinstance(step, dict):
                issues.append("step is not an object")
                break
            title = _clean(step.get("title"), MAX_TITLE)
            detail = _clean(step.get("detail"), MAX_DETAIL)
            if not title or not detail:
                issues.append("empty step")
                break
            steps.append({"title_en": title, "detail_en": detail})
    if not summary:
        issues.append("empty summary")
    raw_cited = answer.get("cited_article_ids")
    cited = [str(i) for i in (raw_cited if isinstance(raw_cited, list) else [])
             if str(i) in allowed_ids]
    if allowed_ids and not cited:
        if not raw_cited and default_id in allowed_ids:
            cited = [default_id]
        else:
            issues.append("no valid protocol cited")
    text = " ".join([summary, *(s["title_en"] + " " + s["detail_en"] for s in steps)])
    if not text.isascii():
        issues.append("non-English characters")
    if _BLOCKED.search(text):
        issues.append("blocked word")
    if issues:
        return None, issues
    return Guidance(summary, steps, cited, "assistant", LLM_MODEL), []


def fallback(finding: dict, group: str, article: dict | None) -> Guidance:
    """Deterministic guidance from validated care steps; always available."""
    names = ", ".join(m["display_name_en"].lower() for m in finding["top_metrics"][:2])
    summary = f"{finding['pattern_label_en']} detected today"
    summary += f", mainly in {names}." if names else "."
    if article:
        summary += f" Follow the {article['title_en']} protocol."
    steps = [dict(s) for s in CARE_STEPS[group]]
    return Guidance(summary, steps, [article["id"]] if article else [], "fallback",
                    "care-steps")


def generate_guidance(finding: dict, articles: list[dict], group: str,
                      client: httpx.Client | None = None) -> Guidance:
    """Ask the local model; fall back to validated care steps if anything goes wrong."""
    primary = next((a for a in articles if a["id"] == finding.get("article_id")),
                   articles[0] if articles else None)
    payload = {
        "model": LLM_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": build_prompt(finding, articles),
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        if client is not None:
            response = client.post(f"{LLM_URL}/api/generate", json=payload)
        else:
            # Own client: closed right after the call so no connection stays open.
            with httpx.Client(timeout=LLM_TIMEOUT_SEC) as http:
                response = http.post(f"{LLM_URL}/api/generate", json=payload)
        response.raise_for_status()
        answer = json.loads(response.json()["response"])
        guidance, issues = validate(answer, {a["id"] for a in articles},
                                    primary["id"] if primary else None)
        if guidance:
            return guidance
        result = fallback(finding, group, primary)
        result.issues = issues
        return result
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as exc:
        result = fallback(finding, group, primary)
        result.issues = [f"assistant unavailable: {type(exc).__name__}"]
        return result


# -- Heart and lung sound sessions (M5) ---------------------------------------------------
def build_acoustic_prompt(session: dict, context: dict, articles: list[dict]) -> str:
    """Prompt for one suspicious recording, cross-checked with oxygen, fitness and cabin air."""
    probs = ", ".join(f"{k.replace('_', ' ')} {v:g}%" for k, v in session["probabilities"].items())
    related = "; ".join(f"{name}: {value}" for name, value in context.items() if value is not None)
    protocols = "\n".join(
        f"- id={a['id']} | {a['title_en']} | steps: "
        + " / ".join(f"{s['title_en']}: {s['detail_en']}" if s.get("detail_en") else s["title_en"]
                     for s in a["steps"])
        + f" | call the physician when: {a['escalation_en']}"
        for a in articles
    )
    organ = "heart" if session["organ_type"] == "CARDIAC" else "lungs"
    return (
        f"A 30-second {organ} recording at the {session['site'].replace('_', ' ')} spot "
        f"sounds like: {session['label_en']} ({session['confidence_pct']:g}% likely; "
        f"other sounds: {probs}). Rate: {session['rate_text']}.\n"
        f"Related readings: {related or 'none recorded'}.\n"
        f"Protocols you may cite:\n{protocols}\n"
        "This is a screening suspicion, not a diagnosis. Choose the 3 listed steps that fit "
        "best and restate them simply. Write the JSON answer now."
    )


def acoustic_fallback(session: dict, group: str, article: dict | None) -> Guidance:
    """Deterministic interpretation from validated care steps; always available."""
    organ = "heart" if session["organ_type"] == "CARDIAC" else "lung"
    summary = (
        f"{session['label_en']} heard at the {session['site'].replace('_', ' ')} spot "
        f"({session['confidence_pct']:g}% likely) on a 30-second {organ} recording. "
        "The crew physician will listen to the recording before any change is made."
    )
    steps = [dict(s) for s in CARE_STEPS[group]]
    return Guidance(summary, steps, [article["id"]] if article else [], "fallback", "care-steps")


def generate_acoustic_guidance(session: dict, context: dict, articles: list[dict], group: str,
                               client: httpx.Client | None = None) -> Guidance:
    """Ask the local model about a recording; fall back to validated care steps on any issue."""
    primary = articles[0] if articles else None
    payload = {
        "model": LLM_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": build_acoustic_prompt(session, context, articles),
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        if client is not None:
            response = client.post(f"{LLM_URL}/api/generate", json=payload)
        else:
            with httpx.Client(timeout=LLM_TIMEOUT_SEC) as http:
                response = http.post(f"{LLM_URL}/api/generate", json=payload)
        response.raise_for_status()
        answer = json.loads(response.json()["response"])
        guidance, issues = validate(answer, {a["id"] for a in articles},
                                    primary["id"] if primary else None)
        if guidance:
            return guidance
        result = acoustic_fallback(session, group, primary)
        result.issues = issues
        return result
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as exc:
        result = acoustic_fallback(session, group, primary)
        result.issues = [f"assistant unavailable: {type(exc).__name__}"]
        return result
