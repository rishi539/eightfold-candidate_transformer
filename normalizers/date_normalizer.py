"""
Date normaliser — converts various human-readable date strings to YYYY-MM.

Handles formats such as:
    * ``Jan 2020``
    * ``01/2020``
    * ``2020-01``
    * ``January 2020``
    * ``2020-01-15``
    * ``Jan 15, 2020``
    * ``15 Jan 2020``
    * ``2020``
    * ``Present`` / ``Current`` → None (intentional)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Month-name lookup
# ------------------------------------------------------------------ #
_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Compiled patterns (ordered from most specific → least specific)
# ISO full date: 2020-01-15
_RE_ISO_FULL = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
# ISO year-month: 2020-01  or  2020/01
_RE_ISO_YM = re.compile(r"^(\d{4})[-/](\d{1,2})$")
# MM/YYYY or MM-YYYY
_RE_MM_YYYY = re.compile(r"^(\d{1,2})[/-](\d{4})$")
# Month-name Year: Jan 2020, January 2020
_RE_MON_YEAR = re.compile(
    r"^([A-Za-z]+)\s*,?\s*(\d{4})$"
)
# Day Month-name Year: 15 Jan 2020
_RE_DAY_MON_YEAR = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]+)\s*,?\s*(\d{4})$"
)
# Month-name Day, Year: Jan 15, 2020
_RE_MON_DAY_YEAR = re.compile(
    r"^([A-Za-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})$"
)
# Bare year: 2020
_RE_YEAR_ONLY = re.compile(r"^(\d{4})$")

# Strings that mean "no end date"
_PRESENT_TOKENS = frozenset({
    "present", "current", "now", "ongoing", "till date", "to date",
    "today", "existing", "cont", "continued",
})


def normalize_date(raw: str) -> Optional[str]:
    """Normalise a raw date string to ``YYYY-MM`` format.

    Parameters
    ----------
    raw:
        Human-readable date string (see module docstring for examples).

    Returns
    -------
    str | None
        A ``YYYY-MM`` string, or ``None`` if the input is invalid,
        empty, or represents an ongoing / "present" date.
    """
    if not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # "Present" / "Current" etc. → None
    if cleaned.lower() in _PRESENT_TOKENS:
        return None

    try:
        return _try_parse(cleaned)
    except Exception:  # noqa: BLE001
        logger.debug("Date normalisation failed for %r", raw, exc_info=True)
        return None


def extract_year(raw: str) -> Optional[int]:
    """Extract a 4-digit year from *raw*.

    Useful for education end-year fields where only the year matters.

    Returns
    -------
    int | None
        The year as an integer, or ``None`` if unparseable.
    """
    if not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    if cleaned.lower() in _PRESENT_TOKENS:
        return None

    try:
        # Try the full parse first — it returns YYYY-MM; take the year part.
        result = _try_parse(cleaned)
        if result:
            return int(result.split("-")[0])

        # Last resort: find any 4-digit number that looks like a year.
        match = re.search(r"\b(19|20)\d{2}\b", cleaned)
        if match:
            return int(match.group(0))

        return None
    except Exception:  # noqa: BLE001
        logger.debug("Year extraction failed for %r", raw, exc_info=True)
        return None


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _try_parse(text: str) -> Optional[str]:
    """Attempt to parse *text* into ``YYYY-MM`` using known patterns."""

    # ISO full date: 2020-01-15
    m = _RE_ISO_FULL.match(text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # ISO year-month: 2020-01
    m = _RE_ISO_YM.match(text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # MM/YYYY
    m = _RE_MM_YYYY.match(text)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # Month-name Day, Year: Jan 15, 2020
    m = _RE_MON_DAY_YEAR.match(text)
    if m:
        month = _month_number(m.group(1))
        year = int(m.group(3))
        if month and _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # Day Month-name Year: 15 Jan 2020
    m = _RE_DAY_MON_YEAR.match(text)
    if m:
        month = _month_number(m.group(2))
        year = int(m.group(3))
        if month and _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # Month-name Year: Jan 2020 / January 2020
    m = _RE_MON_YEAR.match(text)
    if m:
        month = _month_number(m.group(1))
        year = int(m.group(2))
        if month and _valid_ym(year, month):
            return f"{year:04d}-{month:02d}"

    # Bare year: 2020 → default to January
    m = _RE_YEAR_ONLY.match(text)
    if m:
        year = int(m.group(1))
        if 1900 <= year <= 2100:
            return f"{year:04d}-01"

    return None


def _month_number(name: str) -> Optional[int]:
    """Convert a month name / abbreviation to its number (1–12)."""
    return _MONTH_MAP.get(name.lower())


def _valid_ym(year: int, month: int) -> bool:
    """Quick sanity check on year and month values."""
    return 1900 <= year <= 2100 and 1 <= month <= 12
