import re

_WS_RE = re.compile(r"\s+")
_AGE_UNIT_TO_YEARS = {
    "800": 10.0,  # Decade
    "801": 1.0,  # Year
    "802": 1.0 / 12.0,  # Month
    "803": 1.0 / 52.1786,  # Week
    "804": 1.0 / 365.0,  # Day
    "805": 1.0 / (365.0 * 24.0),  # Hour
}
_DATE_FORMAT_PRECISION = {
    "102": "day",  # YYYYMMDD
    "610": "month",  # YYYYMM
    "602": "year",  # YYYY
}
_NARRATIVE_EVENT_DATE_RE = re.compile(r"CASE EVENT DATE:\s*(\d{4,8})")


def clean_text(value: str | None) -> str | None:
    """Collapse internal whitespace and strip; None/empty stays None."""
    if value is None:
        return None
    cleaned = _WS_RE.sub(" ", value).strip()
    return cleaned or None


def normalize_key(value: str | None) -> str | None:
    """Uppercased, whitespace-collapsed dedup key for drug names / MedDRA PTs."""
    cleaned = clean_text(value)
    return cleaned.upper() if cleaned else None


def split_active_substances(raw_names: list[str]) -> list[str]:
    """Split possibly ';'-delimited active-substance strings into a clean, deduped list."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_names:
        for part in raw.split(";"):
            cleaned = clean_text(part)
            if cleaned and cleaned.upper() not in seen:
                seen.add(cleaned.upper())
                out.append(cleaned)
    return out


def age_to_years(age: str | None, unit_code: str | None) -> float | None:
    """Convert a patientonsetage + patientonsetageunit pair to years.

    Returns None (rather than guessing) when the unit code is missing or
    unrecognized -- an age value without a trustworthy unit is not usable.
    """
    if age is None or unit_code is None:
        return None
    try:
        value = float(age)
    except ValueError:
        return None
    factor = _AGE_UNIT_TO_YEARS.get(unit_code)
    if factor is None:
        return None
    return round(value * factor, 4)


def date_precision(date_format_code: str | None) -> str | None:
    return _DATE_FORMAT_PRECISION.get(date_format_code or "")


def extract_narrative_event_date(narrative_text: str | None) -> str | None:
    if not narrative_text:
        return None
    match = _NARRATIVE_EVENT_DATE_RE.search(narrative_text)
    return match.group(1) if match else None
