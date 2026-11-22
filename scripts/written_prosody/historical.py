"""Extract historical reading evidence from a matching Stage 7 text JSON report."""

from collections import Counter
from hashlib import sha256
import unicodedata


TIERS = ("guangyun", "pingshui")
CANDIDATE_FIELDS = ("id", "lookup_char", "tone", "pingze", "rhyme", "source_revision")


def _han(char):
    name = unicodedata.name(char, "")
    return char == "〇" or name.startswith(("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-"))


def _labels(candidate):
    if not isinstance(candidate, dict):
        raise ValueError("Invalid historical candidate")
    return {key: candidate[key] for key in CANDIDATE_FIELDS if candidate.get(key) is not None}


def _reading(analysis):
    if analysis is None:
        analysis = {}
    if not isinstance(analysis, dict):
        raise ValueError("Invalid historical reading")
    candidates = analysis.get("candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("Invalid historical candidate list")
    selected = analysis.get("selected")
    status = analysis.get("status", "missing")
    if status == "context_reviewed":
        valid = selected is not None and selected in candidates
    elif status == "ambiguous":
        valid = len(candidates) > 1 and selected is None
    elif status in ("single_candidate", "single_variant_candidate"):
        valid = len(candidates) == 1 and selected is None
    else:
        valid = status == "missing" and not candidates and selected is None
    if not valid:
        raise ValueError("Historical reading status does not agree with candidates")
    return {"status": status, "lookup": analysis.get("lookup"),
            "candidates": [_labels(c) for c in candidates],
            "selected": _labels(selected) if selected is not None else None}


def historical_evidence(text, stage7_report):
    """Project text-only Stage 7 v1 output onto blinded, offset-indexed dictionary labels."""
    if not isinstance(stage7_report, dict) or stage7_report.get("schema_version") != 1:
        raise ValueError("Expected a Stage 7 schema-version-1 JSON document")
    if stage7_report.get("audio") is not None:
        raise ValueError("Expected a Stage 7 text-only report")
    body = stage7_report.get("text")
    digest = sha256(text.encode("utf-8")).hexdigest()
    if not isinstance(body, dict) or body.get("text") != text or body.get("text_sha256") != digest:
        raise ValueError("Stage 7 text or SHA-256 differs from the candidate")
    try:
        references = body["reference"]["historical"]
        raw_slots = [slot for paragraph in body["paragraphs"]
                     for clause in paragraph["clauses"] for slot in clause["slots"]]
        actual = [(slot["offset"], slot["char"]) for slot in raw_slots]
    except (TypeError, KeyError) as exc:
        raise ValueError("Incomplete Stage 7 historical annotations") from exc
    expected = [(i, char) for i, char in enumerate(text) if _han(char)]
    if (any(type(offset) is not int for offset, _ in actual) or actual != expected
            or not isinstance(references, dict)):
        raise ValueError("Stage 7 historical slots or references are inconsistent with the candidate")

    sources = {}
    for tier in TIERS:
        reference = references.get(tier, {})
        sources[tier] = {key: reference.get(key) for key in ("title", "source_url", "revision_id")}
    slots = []
    counts = {tier: Counter() for tier in TIERS}
    for slot in raw_slots:
        readings = slot.get("readings", {})
        if not isinstance(readings, dict):
            raise ValueError("Invalid Stage 7 slot readings")
        row = {"offset": slot["offset"], "char": slot["char"]}
        for tier in TIERS:
            entry = _reading(readings.get(tier))
            row[tier] = entry
            counts[tier][entry["status"]] += 1
        slots.append(row)
    coverage = {
        tier: {"total_han_slots": len(slots), "with_candidates": len(slots) - tally["missing"],
               "missing": tally["missing"], "ambiguous": tally["ambiguous"],
               "context_reviewed": tally["context_reviewed"]}
        for tier, tally in counts.items()
    }
    return {"text_sha256": digest, "offset_unit": "zero-based Unicode code points",
            "sources": sources, "coverage": coverage, "slots": slots}
