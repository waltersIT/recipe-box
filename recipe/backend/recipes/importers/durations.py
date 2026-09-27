"""Turn human ("1 hr 15 mins") and ISO 8601 ("PT1H15M") durations into minutes."""

import re

_ISO = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$",
    re.I,
)

_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

# A number (optionally "1 1/2", "1½", "1.5"), optionally a range ("20-25", "20 to 25").
_NUM = r"\d+(?:\.\d+)?(?:\s+\d/\d|\s*[½¼¾⅓⅔])?|\d/\d|[½¼¾⅓⅔]"
_PART = re.compile(
    rf"(?P<num>{_NUM})(?:\s*(?:-|–|—|to)\s*(?P<num2>{_NUM}))?\s*"
    r"(?P<unit>days?|d(?![a-z])|hours?|hrs?|h(?![a-z])|minutes?|mins?|m(?![a-z]))",
    re.I,
)


def _to_float(text: str) -> float:
    text = text.strip()
    total = 0.0
    for ch, value in _FRACTIONS.items():
        if ch in text:
            total += value
            text = text.replace(ch, "").strip()
    for piece in text.split():
        if "/" in piece:
            num, den = piece.split("/", 1)
            total += float(num) / float(den)
        elif piece:
            total += float(piece)
    return total


def parse_duration(value) -> int | None:
    """Return a duration in whole minutes, or None if it can't be understood.

    Ranges ("20 to 25 minutes") resolve to the upper bound.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    text = str(value).strip()
    if not text:
        return None

    iso = _ISO.match(text)
    if iso and any(iso.groupdict().values()):
        parts = {k: float(v) for k, v in iso.groupdict().items() if v}
        minutes = (
            parts.get("days", 0) * 1440
            + parts.get("hours", 0) * 60
            + parts.get("minutes", 0)
            + parts.get("seconds", 0) / 60
        )
        return round(minutes) or None

    minutes = 0.0
    found = False
    for match in _PART.finditer(text):
        found = True
        amount = _to_float(match.group("num2") or match.group("num"))
        unit = match.group("unit").lower()
        if unit.startswith("d"):
            minutes += amount * 1440
        elif unit.startswith("h"):
            minutes += amount * 60
        else:
            minutes += amount
    if found:
        return round(minutes) or None

    # A bare number is assumed to be minutes ("45").
    if re.fullmatch(r"\d{1,4}", text):
        return int(text) or None
    return None


def format_minutes(minutes: int | None) -> str:
    if not minutes:
        return ""
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{hours} hr {mins} min"
    if hours:
        return f"{hours} hr"
    return f"{mins} min"
