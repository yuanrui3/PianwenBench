"""Evaluate explicit line and Han-character positions against 平水韵 readings."""

from collections import defaultdict
from unicodedata import name


AXES = ("tone", "rhyme_group", "character")


def _positive_int(value):
    return type(value) is int and value > 0


def _han(value):
    return isinstance(value, str) and len(value) == 1 and (
        value == "〇" or name(value, "").startswith(("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-"))
    )


def _validate_slot(slot):
    if not isinstance(slot, dict) or slot.keys() - {"line", "position", *AXES}:
        raise ValueError("a slot must be an object with recognized fields")
    if not _positive_int(slot.get("line")):
        raise ValueError("line must be a positive integer")
    position = slot.get("position")
    if position != "end" and not _positive_int(position):
        raise ValueError("position must be a positive integer or 'end'")
    if not any(axis in slot for axis in AXES):
        raise ValueError("a slot must declare at least one constraint")
    if "tone" in slot and slot["tone"] not in ("平", "仄"):
        raise ValueError("tone must be 平 or 仄")
    if "rhyme_group" in slot and not (
        isinstance(slot["rhyme_group"], str) and slot["rhyme_group"].strip()
    ):
        raise ValueError("rhyme_group must be a nonempty edition label")
    if "character" in slot and not _han(slot["character"]):
        raise ValueError("character must be one Han character")


def validate_slots(slots):
    """Check the semantics shared by item validation and form reports."""
    if not isinstance(slots, list) or not slots:
        raise ValueError("at least one explicit slot is required")
    seen = set()
    for slot in slots:
        _validate_slot(slot)
        coordinate = (slot["line"], slot["position"])
        if coordinate in seen:
            raise ValueError("duplicate slot: combine constraints at the same declared position")
        seen.add(coordinate)


def _validate_annotation(annotation):
    if not isinstance(annotation, dict) or not _han(annotation.get("char")):
        raise ValueError("invalid character annotation")
    candidates = annotation.get("candidates")
    selected = annotation.get("selected")
    if not isinstance(candidates, list):
        raise ValueError("source candidates must be a list")
    for reading in candidates:
        if not (
            isinstance(reading, dict)
            and reading.get("pingze") in ("平", "仄")
            and isinstance(reading.get("rhyme"), str)
            and reading["rhyme"].strip()
        ):
            raise ValueError("incomplete 平水韵 candidate")
    if selected is not None and selected not in candidates:
        raise ValueError("contextual reading must belong to the source candidates")


def _possible_readings(annotation, slots):
    """Produce comparable observations, keeping every candidate's fields together."""
    if annotation is None:
        return [{}], "missing"
    char = annotation["char"]
    candidates = annotation["candidates"]
    selected = annotation.get("selected")
    if candidates:
        readings = [selected] if selected is not None else candidates
        status = "single_candidate" if len(candidates) == 1 else "ambiguous"
        if selected is not None:
            status = "context_reviewed"
        return [
            {"character": char, "tone": reading["pingze"], "rhyme_group": reading["rhyme"]}
            for reading in readings
        ], status

    # A gap can match a requested group, or another group of either tone.
    # The volume of a full 平水韵 label fixes its tone even in this case.
    groups = {slot["rhyme_group"] for slot in slots if "rhyme_group" in slot}
    possibilities = []
    for group in [None, *groups]:
        tones = ("平", "仄")
        if group and group.startswith(("上平", "下平")):
            tones = ("平",)
        elif group and group.startswith(("上聲", "去聲", "入聲")):
            tones = ("仄",)
        for tone in tones:
            possibilities.append({"character": char, "tone": tone, "rhyme_group": group})
    return possibilities, "dictionary_gap"


def _tally(slots, possibilities, axis=None):
    """Take extrema after evaluating all constraints on one shared reading."""
    requirements = [
        {key: slot[key] for key in AXES if key in slot and (axis is None or key == axis)}
        for slot in slots if axis is None or axis in slot
    ]
    counts = [
        sum(all(reading.get(key) == value for key, value in required.items()) for required in requirements)
        for reading in possibilities
    ]
    return {"denominator": len(requirements), "lower": min(counts), "upper": max(counts)}


def evaluate_form(slots, lines):
    """Return attainable counts for declared slots and each of their three axes.

    Both coordinates are one-based. Lines must already be aligned to the
    declarations; use an empty list or None for an omitted interior line. Each
    observed line is a list of {char, candidates, selected} annotations in Han
    character order. Rhyme labels are matched literally against the source.
    """
    validate_slots(slots)
    if not isinstance(lines, list):
        raise ValueError("aligned lines must be a list")
    for line in lines:
        if line is None:
            continue
        if not isinstance(line, list):
            raise ValueError("each aligned line must be a list of character annotations or null")
        for annotation in line:
            _validate_annotation(annotation)
    occurrences = defaultdict(list)
    for index, slot in enumerate(slots):
        line_number, position = slot["line"], slot["position"]
        line = lines[line_number - 1] if line_number <= len(lines) else None
        actual_position = len(line or []) if position == "end" else position
        occurrences[line_number, actual_position].append(index)

    totals = {axis: {"denominator": 0, "lower": 0, "upper": 0} for axis in (None, *AXES)}
    evidence = [None] * len(slots)
    missing_slots, dictionary_gaps = [], []
    for (line_number, position), indices in occurrences.items():
        line = lines[line_number - 1] if line_number <= len(lines) else None
        annotation = line[position - 1] if line and position <= len(line) else None
        declarations = [slots[index] for index in indices]
        possibilities, reading_status = _possible_readings(annotation, declarations)
        for axis, total in totals.items():
            for key, value in _tally(declarations, possibilities, axis).items():
                total[key] += value
        for index in indices:
            slot = slots[index]
            coordinate = {"line": line_number, "position": slot["position"]}
            if reading_status == "missing":
                missing_slots.append(coordinate)
            if reading_status == "dictionary_gap":
                dictionary_gaps.append(coordinate)
            evidence[index] = {
                "declaration": dict(slot),
                "observed": annotation,
                "reading_status": reading_status,
                **_tally([slot], possibilities),
                "axes": {axis: _tally([slot], possibilities, axis) for axis in AXES if axis in slot},
            }
    joint = totals.pop(None)
    return {
        **joint, "axes": totals, "slots": evidence,
        "missing_slots": missing_slots, "dictionary_gaps": dictionary_gaps,
    }
