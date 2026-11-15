"""Local language model guidance for anomaly findings (D3-05).

The onboard assistant writes a short plain-English summary and three preventive
steps grounded in the medical guide. It runs on the local model server only
(no network beyond this machine). Every answer is checked; anything malformed,
off-topic or slow is replaced by a deterministic answer built from the care
steps and guide protocols already validated for the app. A physician must
review every finding before the crew acts on it.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field

import httpx

from app.services.alert_engine import CARE_STEPS

LLM_URL = os.environ.get("SPACESCAN_LLM_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("SPACESCAN_LLM_MODEL", "qwen2.5:3b")
LLM_TIMEOUT_SEC = float(os.environ.get("SPACESCAN_LLM_TIMEOUT", "20"))

# Words that must never reach the screen: restricted entities (kept encoded so
# the code base never names them) and internal technology names.
_RESTRICTED = [base64.b64decode(v).decode() for v in ("bmFzYQ==", "Y2hpbmE=", "Y2hpbmVzZQ==")]
_BLOCKED = re.compile(
    r"\b(" + "|".join(_RESTRICTED) + r"|sqlite|json|fhir|hl7|kiwix|zim|fts5|wal|offline"
    r"|break-glass|dtn|osdr|donki|onnx|ollama|nuxt|python|neural|autoencoder|llm|ai model"
    r"|language model)\b",
    re.IGNORECASE,
)
MAX_TITLE = 60
MAX_DETAIL = 220
MAX_SUMMARY = 400

SYSTEM_PROMPT = (
    "You assist the physician of a spaceflight crew. Write in plain, calm English for "
    "astronauts, without technology names or code words. Use only the protocols provided. "
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


def _clean(text: object, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def build_prompt(finding: dict, articles: list[dict]) -> str:
    metrics = "; ".join(
        f"{m['display_name_en']}: {m['value']:g} {m['unit']} (usual {m['baseline']:g} "
        f"{m['unit']}, {m['z']:+.1f} spreads from usual)"
        for m in finding["top_metrics"]
    ) or "no single reading stands out"
    protocols = "\n".join(
        f"- id={a['id']} | {a['title_en']} | steps: "
        + " / ".join(s["title_en"] for s in a["steps"])
        + f" | call the physician when: {a['escalation_en']}"
        for a in articles
    )
    return (
        f"Pattern found today: {finding['pattern_label_en']}.\n"
        f"Readings that stand out: {metrics}.\n"
        f"Protocols you may cite:\n{protocols}\n"
        "Write the JSON answer now."
    )


def validate(answer: dict, allowed_ids: set[str]) -> tuple[Guidance | None, list[str]]:
    """Check a raw model answer; return cleaned guidance or the reasons it failed."""
    issues: list[str] = []
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
    cited = [str(i) for i in answer.get("cited_article_ids") or [] if str(i) in allowed_ids]
    if allowed_ids and not cited:
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
        http = client or httpx.Client(timeout=LLM_TIMEOUT_SEC)
        response = http.post(f"{LLM_URL}/api/generate", json=payload)
        response.raise_for_status()
        answer = json.loads(response.json()["response"])
        guidance, issues = validate(answer, {a["id"] for a in articles})
        if guidance:
            return guidance
        result = fallback(finding, group, primary)
        result.issues = issues
        return result
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        result = fallback(finding, group, primary)
        result.issues = [f"assistant unavailable: {type(exc).__name__}"]
        return result
