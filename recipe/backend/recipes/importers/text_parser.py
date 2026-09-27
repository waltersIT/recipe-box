"""Rule-based recipe extraction from lines of text.

Used for PDFs, screenshots and web pages without structured recipe data when
Claude isn't configured (or as a fallback when it fails). It looks for the
usual section headings ("Ingredients", "Directions", "Notes"...), pulls out
times/servings, and falls back to spotting ingredient-shaped lines when a
recipe has no headings at all.
"""

import re

from .draft import RecipeDraft
from .durations import parse_duration
from .layout import Line

# --- Patterns -----------------------------------------------------------------

_BULLETS = re.compile(
    r"^(?:[•‣⁃∙·▪▫■□▢○●◦"
    r"☐☑☒✓✔❏❑❒◻◽*\-–—>»]+\s*)+"
)
# Checkboxes in front of ingredients are often read by OCR as "O" or "口".
_CHECKBOX = re.compile(r"^(?:[Oo口□]|\[\s?\])\s+(?=\S)")

_HEADER_WORDS = {
    "ingredients": r"ingredients?(?: list)?|what you(?:'|’)?ll need|you(?:'|’)?ll need|you will need|shopping list",
    "instructions": r"instructions?|directions?|method|preparation|steps|how to make(?: it| this)?|procedure|cooking instructions",
    "notes": r"(?:recipe |cook(?:'|’)?s |chef(?:'|’)?s |baker(?:'|’)?s )?notes?|tips?(?: (?:and|&) tricks)?|variations?|storage(?: instructions)?|make ahead",
    "nutrition": r"nutrition(?:al)?(?: facts| information| info)?(?: per serving)?",
    "equipment": r"equipment|tools|you(?:'|’)?ll also need",
}
_HEADER_SUFFIX = r"(?:\s*(?:\([^)]*\)|\d+x|us customary|metric|[:\-–]))*"
_HEADERS = [
    (name, re.compile(rf"^(?:{words}){_HEADER_SUFFIX}\s*$", re.I)) for name, words in _HEADER_WORDS.items()
]

_TIME_LABEL = re.compile(
    r"\b(?P<label>prep(?:aration)?|cook(?:ing)?|bake|baking|total|active|hands[- ]on|inactive|chill(?:ing)?|rest(?:ing)?)"
    r"\s*(?:time)\b\s*:?|\b(?P<label2>prep|cook|bake|total)\s*:|\b(?P<ready>ready in)\b",
    re.I,
)
_TIME_KIND = {
    "prep": "prep_time", "preparation": "prep_time", "active": "prep_time", "hands-on": "prep_time",
    "hands on": "prep_time", "cook": "cook_time", "cooking": "cook_time", "bake": "cook_time",
    "baking": "cook_time", "total": "total_time", "ready in": "total_time",
}
_SERVINGS = re.compile(r"^(?:serves|servings?|yields?|makes|portions?)\b\s*[:\-]?\s*(?P<value>.*)$", re.I)
_SERVINGS_WORD = re.compile(r"\b(?:serves|servings?|yields?|makes)\b\s*:?", re.I)
_SERVINGS_BARE = re.compile(r"^(?P<value>\d+(?:\s*(?:-|–|to)\s*\d+)?\s+(?:servings?|portions?|people))$", re.I)
_TAG_LINE = re.compile(r"^(?:course|cuisine|category|categories)\s*:?\s*(?P<value>.+)$", re.I)
_AUTHOR_LINE = re.compile(r"^(?:by|author|recipe by)\s*:?\s+(?P<value>[A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+){0,3})$")
_SKIP_META = re.compile(r"^(?:keywords?|calories|equipment)\s*:", re.I)
_METADATA_LABEL_ONLY = re.compile(
    r"^(?:(?:prep(?:aration)?|cook(?:ing)?|bake|total|active|inactive|chill|rest)\s*(?:time)?|servings?|serves|yields?|makes|calories|course|cuisine)\s*:?$",
    re.I,
)
# One value in a row of values under a row of labels: "1 hr 27 mins", "15 mins", "24 cookies".
_VALUE_TOKEN = re.compile(
    r"\d+(?:\s*(?:-|–|to)\s*\d+)?\s*(?:(?:days?|hours?|hrs?|h)\b(?:\s*\d+\s*(?:minutes?|mins?|m)\b)?|(?:minutes?|mins?|m)\b)"
    r"|\d+(?:\s*(?:-|–|to)\s*\d+)?(?:\s+[a-z]+)?",
    re.I,
)

_JUNK = [
    re.compile(p, re.I)
    for p in (
        r"^\d{1,2}:\d{2}(?:\s?[ap]m)?$",  # phone status-bar clock
        r"^(?:\d{1,3}\s?%|lte|5g|4g|wi-?fi|aa)$",
        r"^(?:jump to recipe|jump to video|print(?: recipe)?|pin(?: recipe| it)?|save(?: recipe)?|saved|share|"
        r"rate(?: this recipe)?|email|comments?|leave a (?:comment|review)|skip to (?:content|recipe|main content)|"
        r"cook mode|prevent your screen from going dark|advertisement|ad|sponsored|video|watch(?: the)? video|"
        r"reviews?|\d+ (?:reviews?|comments?|ratings?)|opens in a new window|scroll to continue.*|"
        r"(?:us customary|metric)(?:\s+(?:us customary|metric))?|log ?in|sign ?in|subscribe|menu|search)$",
        r"^(?:\d(?:\.\d)?x\s*){2,}$",  # recipe scaling buttons: 1x 2x 3x
        # Star ratings ("★★★★★ 4.9 from 212 votes", often OCR'd as "00000 4.9 ...").
        r"^[\W0Oo★☆]*\s*\d(?:\.\d+)?\s*(?:stars?|out of 5)?\s*(?:from|\(|-)\s*[\d,]+\s*(?:votes?|ratings?|reviews?)?\)?$",
        r"^(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$",  # bare URLs / domains
        r"^page \d+(?: of \d+)?$",
        r"^[^\w½¼¾⅓⅔]+$",  # only symbols (star ratings, dividers)
    )
]

_QUANTITY_START = re.compile(
    r"^(?:\d|[½¼¾⅓⅔⅛⅜⅝⅞]|an?\s+(?:few|pinch|dash|handful|couple|small|medium|large|big)\b|"
    r"(?:one|two|three|four|five|six|eight|ten|twelve|half|pinch|dash|handful|juice of|zest of)\b)",
    re.I,
)
_UNITS = re.compile(
    r"\b(?:cups?|tbsps?|tablespoons?|tsps?|teaspoons?|oz|ounces?|lbs?|pounds?|grams?|g|kg|ml|"
    r"milliliters?|liters?|litres?|pints?|quarts?|cloves?|cans?|packages?|sticks?|slices?|pinch(?:es)?|"
    r"dash(?:es)?|bunch(?:es)?|sprigs?|stalks?|fillets?)\b",
    re.I,
)
_LOOSE_INGREDIENT = re.compile(r"\b(?:to taste|for (?:garnish|serving|dusting)|optional)\b", re.I)
_STEP_NUMBER = re.compile(r"^(?:step\s*)?(\d{1,2})\s*[.):]\s+(?=\S)|^step\s*(\d{1,2})\b\s*[:.\-–]?\s*", re.I)
# "1. Heat the oil..." - a numbered step, not "1 onion".
_NUMBERED_STEP = re.compile(r"^(?:step\s*)?\d{1,2}[.):]\s+[A-Z][a-z]+\b(?!\s*(?:cups?|tbsps?|tsps?|oz|lbs?|g)\b).{20,}", re.I | re.S)
_LONE_NUMBER = re.compile(r"^(?:step\s*)?\d{1,2}[.):]?$", re.I)
_CONTINUES = re.compile(r"(?:[,(/&\-–]|\b(?:and|or|of|to|into|with|plus|for|in|at))$", re.I)
_SENTENCE_END = re.compile(r"[.!?][\"'”’)]*$")
_NUTRIENT = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z ]{1,25}?)\s*:?\s*(?P<value>\d+(?:\.\d+)?\s*(?:kcal|cal|mg|g|%|iu)\b)", re.I
)


# --- Line helpers -------------------------------------------------------------


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_bullet(text: str) -> tuple[str, bool]:
    stripped = _BULLETS.sub("", text)
    return stripped.strip(), stripped != text


def is_junk(text: str) -> bool:
    return any(p.match(text) for p in _JUNK)


def header_kind(text: str) -> str | None:
    text = _strip_bullet(text)[0]
    if len(text) > 50:
        return None
    for name, pattern in _HEADERS:
        if pattern.match(text):
            return name
    return None


def looks_like_ingredient(text: str) -> bool:
    if len(text) > 120 or (_SENTENCE_END.search(text) and len(text) > 60):
        return False
    if _NUMBERED_STEP.match(text):
        return False
    if _QUANTITY_START.match(text):
        return True
    if len(text) <= 50 and _UNITS.search(text) and not text.endswith("."):
        return True
    return len(text) <= 60 and bool(_LOOSE_INGREDIENT.search(text))


def _is_subheading(text: str) -> bool:
    words = text.split()
    if not words or len(words) > 7 or _QUANTITY_START.match(text):
        return False
    if text.endswith(":"):
        return True
    return bool(re.match(r"^for (?:the )?[a-z][\w\s'’&-]{1,40}$", text, re.I)) and not re.search(r"\d", text)


def _heading(text: str) -> str:
    return "# " + text.rstrip(":").strip()


# --- Metadata -----------------------------------------------------------------


def _merge_label_rows(lines: list[Line]) -> list[Line]:
    """Join 'PREP TIME' / '10 mins' style label and value rows into one line."""
    out: list[Line] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt is not None:
            labels = list(_TIME_LABEL.finditer(line.text)) + list(
                re.finditer(r"\b(?:servings?|serves|yields?)\b", line.text, re.I)
            )
            leftover = _TIME_LABEL.sub("", line.text)
            leftover = re.sub(r"\b(?:servings?|serves|yields?|time)\b|[:|]", "", leftover, flags=re.I).strip()
            if len(labels) >= 2 and not leftover:
                labels.sort(key=lambda m: m.start())
                values = _VALUE_TOKEN.findall(nxt.text)
                if len(values) == len(labels):
                    for label, value in zip(labels, values):
                        out.append(Line(text=f"{label.group(0).rstrip(':')}: {value}", gap_before=False))
                    i += 2
                    continue
            if _METADATA_LABEL_ONLY.match(line.text) and len(nxt.text) <= 30 and re.match(r"^\d", nxt.text):
                out.append(Line(text=f"{line.text.rstrip(':')}: {nxt.text}", gap_before=line.gap_before))
                i += 2
                continue
        out.append(line)
        i += 1
    return out


def _take_metadata(text: str, draft: RecipeDraft) -> bool:
    """If the line is recipe metadata (times, servings, course...), record it and return True."""
    if len(text) > 100:
        return False
    if _SKIP_META.match(text):
        if text.lower().startswith("calories"):
            _take_nutrition(text, draft)
        return True
    labels = list(_TIME_LABEL.finditer(text))
    if labels and labels[0].start() == 0:
        # "Prep Time: 15 mins  Cook Time: 25 mins  Serves 4" - split at each label.
        labels = sorted(labels + list(_SERVINGS_WORD.finditer(text)), key=lambda m: m.start())
        for index, match in enumerate(labels):
            end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
            value = text[match.end():end]
            if match.re is _SERVINGS_WORD:
                _set_servings(value, draft)
                continue
            minutes = parse_duration(value)
            label = (match.group("label") or match.group("label2") or match.group("ready") or "").lower()
            kind = _TIME_KIND.get(label)
            if kind and minutes and getattr(draft, kind) is None:
                setattr(draft, kind, minutes)
        return True
    servings = _SERVINGS.match(text) or _SERVINGS_BARE.match(text)
    if servings:
        value = servings.group("value").strip(" :-")
        _set_servings(value, draft)
        return bool(value) or text.lower().rstrip(":") in {"servings", "serves", "yield", "makes"}
    tag = _TAG_LINE.match(text)
    if tag:
        for name in re.split(r"[,/|;]", tag.group("value")):
            name = name.strip()
            if name and name.lower() not in {t.lower() for t in draft.tags} and len(name) <= 40:
                draft.tags.append(name)
        return True
    author = _AUTHOR_LINE.match(text)
    if author:
        draft.author = draft.author or author.group("value")
        return True
    return False


def _set_servings(value: str, draft: RecipeDraft) -> None:
    value = value.strip(" :-|")
    if value and not draft.servings and len(value) <= 40:
        draft.servings = f"{value} servings" if re.fullmatch(r"\d+(?:\s*(?:-|–|to)\s*\d+)?", value) else value


def _take_nutrition(text: str, draft: RecipeDraft) -> None:
    for match in _NUTRIENT.finditer(text):
        name = match.group("name").strip().title()
        if name.lower() in {"serving", "serving size", "servings"}:
            continue
        draft.nutrition.setdefault(name, match.group("value").strip())


# --- Section builders ---------------------------------------------------------


def _fix_ocr(text: str) -> str:
    """Common OCR misreads in ingredient lines."""
    text = re.sub(r"(\d|[½¼¾⅓⅔])\s*Ib(s?)\b", r"\1 lb\2", text)  # "2 Ib" -> "2 lb"
    return re.sub(r"^[lI](?=\s+(?:cups?|tbsps?|tablespoons?|tsps?|teaspoons?|lbs?|oz|pounds?|large|medium|small)\b)", "1", text)


def _build_ingredients(lines: list[Line]) -> list[str]:
    items: list[str] = []
    previous: Line | None = None
    for line in lines:
        text, had_bullet = _strip_bullet(line.text)
        text = _fix_ocr(_CHECKBOX.sub("", text).strip())
        if not text:
            continue
        if _is_subheading(text):
            items.append(_heading(text))
            previous = None
            continue
        if items and previous is not None and not had_bullet and not items[-1].startswith("# "):
            prior = items[-1]
            unbalanced = prior.count("(") > prior.count(")")
            wrapped = text[:1].islower() and not _QUANTITY_START.match(text) and (
                previous.fills_width
                # A lone lowercase word ("temperature") is the tail of a wrapped line.
                or (len(text.split()) == 1 and not looks_like_ingredient(text))
            )
            if _CONTINUES.search(prior) or unbalanced or text.startswith(")") or wrapped:
                items[-1] = f"{prior} {text}"
                previous = line
                continue
        items.append(text)
        previous = line
    return items


def _paragraphs(lines: list[Line]) -> list[str]:
    """Group wrapped lines into paragraphs (steps or notes)."""
    paragraphs: list[str] = []
    current = ""
    previous: Line | None = None
    for line in lines:
        text, had_bullet = _strip_bullet(line.text)
        if not text:
            continue
        if _is_subheading(text) and len(text) < 50:
            if current:
                paragraphs.append(current)
            paragraphs.append(_heading(text))
            current, previous = "", None
            continue
        starts_new = (
            not current
            or line.gap_before
            or had_bullet
            or (_SENTENCE_END.search(current) and previous is not None and not previous.fills_width)
        )
        if starts_new:
            if current:
                paragraphs.append(current)
            current = text
        else:
            current = f"{current} {text}"
        previous = line
    if current:
        paragraphs.append(current)
    return paragraphs


def _build_steps(lines: list[Line]) -> list[str]:
    cleaned = [(line, _strip_bullet(line.text)[0]) for line in lines]
    numbered = sum(1 for _, text in cleaned if _STEP_NUMBER.match(text) or _LONE_NUMBER.match(text))
    if numbered < 2:
        return _paragraphs(lines)

    steps: list[str] = []
    current: str | None = None

    def flush():
        nonlocal current
        if current and current.strip():
            steps.append(current.strip())
        current = None

    for _, text in cleaned:
        if not text:
            continue
        if _LONE_NUMBER.match(text):
            flush()
            current = ""
            continue
        match = _STEP_NUMBER.match(text)
        if match:
            flush()
            current = text[match.end():].strip()
        elif _is_subheading(text) and len(text) < 50:
            flush()
            steps.append(_heading(text))
        elif current is None:
            current = text
        else:
            current = f"{current} {text}".strip()
    flush()
    return steps


def _looks_like_step(text: str) -> bool:
    return bool(_STEP_NUMBER.match(text)) or (
        len(text) >= 80 and bool(_SENTENCE_END.search(text)) and not _QUANTITY_START.match(text)
    )


def _find_ingredient_block(lines: list[Line]) -> tuple[int, int] | None:
    """Longest run of ingredient-looking lines (tolerating one odd line inside)."""
    best = None
    i = 0
    while i < len(lines):
        if not looks_like_ingredient(_strip_bullet(lines[i].text)[0]):
            i += 1
            continue
        start = end = i
        misses = 0
        j = i + 1
        while j < len(lines):
            text = _strip_bullet(lines[j].text)[0]
            if looks_like_ingredient(text) or _is_subheading(text):
                end = j
                misses = 0
            elif len(text) <= 60 and not _SENTENCE_END.search(text) and misses == 0:
                misses = 1
            else:
                break
            j += 1
        count = end - start + 1
        if count >= 2 and (best is None or count > best[1] - best[0] + 1):
            best = (start, end)
        i = end + 1
    return best


def _pick_title(candidates: list[Line]) -> int | None:
    usable = [
        (i, line)
        for i, line in enumerate(candidates)
        if 2 <= len(line.text) <= 120
        and not _SENTENCE_END.search(line.text.rstrip("!"))
        and not _QUANTITY_START.match(line.text)
    ]
    if not usable:
        return None
    tallest = max(usable, key=lambda item: item[1].height)
    if tallest[1].height >= 1.25:
        return tallest[0]
    return usable[0][0]


# --- Entry point --------------------------------------------------------------


def parse_recipe_text(lines: list[Line]) -> tuple[RecipeDraft, list[str]]:
    """Parse ordered lines into a RecipeDraft. Returns (draft, warnings)."""
    draft = RecipeDraft()
    warnings: list[str] = []

    cleaned: list[Line] = []
    for line in lines:
        text = _clean(line.text)
        if text and not is_junk(text):
            cleaned.append(Line(text=text, height=line.height, gap_before=line.gap_before, fills_width=line.fills_width))
    cleaned = _merge_label_rows(cleaned)

    sections: dict[str, list[Line]] = {"head": [], "ingredients": [], "instructions": [], "notes": [], "nutrition": [], "equipment": []}
    current = "head"
    saw_header = {"ingredients": False, "instructions": False}
    for line in cleaned:
        kind = header_kind(line.text)
        if kind:
            current = kind
            if kind in saw_header:
                saw_header[kind] = True
            continue
        if current != "instructions" and _take_metadata(_strip_bullet(line.text)[0], draft):
            continue
        if current == "ingredients" and not saw_header["instructions"] and _looks_like_step(_strip_bullet(line.text)[0]):
            # Steps with no "Directions" heading right after the ingredient list.
            current = "instructions"
        sections[current].append(line)

    head = sections["head"]
    if not saw_header["ingredients"]:
        block = _find_ingredient_block(head)
        if block:
            start, end = block
            sections["ingredients"] = head[start : end + 1]
            if not saw_header["instructions"]:
                sections["instructions"] = head[end + 1 :] + sections["instructions"]
            head = head[:start]
        elif not saw_header["instructions"] and head:
            # No structure at all: first line is the title, the rest are steps.
            sections["instructions"] = head[1:]
            head = head[:1]

    title_index = _pick_title(head[:8])
    if title_index is not None:
        draft.title = head[title_index].text.strip().strip(":")
        description_lines = head[title_index + 1 :]
    else:
        description_lines = head
    draft.description = "\n\n".join(_paragraphs(description_lines)).strip()

    draft.ingredients = _build_ingredients(sections["ingredients"])
    draft.instructions = _build_steps(sections["instructions"])
    draft.notes = "\n\n".join(p.lstrip("# ") for p in _paragraphs(sections["notes"]))
    for line in sections["nutrition"]:
        _take_nutrition(line.text, draft)

    if not draft.title:
        warnings.append("Couldn't tell which line is the title. Please add one.")
    if not draft.ingredients:
        warnings.append("Couldn't find an ingredient list. Please check the source.")
    if not draft.instructions:
        warnings.append("Couldn't find the instructions. Please check the source.")
    return draft, warnings
