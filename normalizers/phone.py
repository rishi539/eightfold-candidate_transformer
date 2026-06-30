"""Phone number normalization to E.164 format.

Handles common international formats using phonenumbers library.
Examples: 9876543210, +91 9876543210, (555) 123-4567, +1-555-123-4567
"""

from typing import Optional
import logging
import re

try:
    import phonenumbers
except ImportError:  # pragma: no cover
    phonenumbers = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Regions to try when no country code provided
_DEFAULT_REGIONS = ("US", "IN")


def normalize_phone(raw: str) -> Optional[str]:
    """Normalize to E.164 format (e.g. +14155552671), or None if invalid."""
    if not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw:
        return None

    if phonenumbers is not None:
        return _normalize_with_phonenumbers(raw)

    return _normalize_fallback(raw)


def _normalize_with_phonenumbers(raw: str) -> Optional[str]:
    """Parse using phonenumbers library with fallback heuristic."""
    try:
        candidate = raw.strip()
        if not candidate:
            return None

        if candidate.startswith("+"):
            try:
                parsed = phonenumbers.parse(candidate, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
            except phonenumbers.NumberParseException:
                pass

            # Fallback: extract digits
            digits = re.sub(r"\D", "", candidate)
            if digits:
                return f"+{digits}"
            return None

        # Try each default region
        for region in _DEFAULT_REGIONS:
            try:
                parsed = phonenumbers.parse(candidate, region)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(
                        parsed, phonenumbers.PhoneNumberFormat.E164
                    )
            except phonenumbers.NumberParseException:
                continue

        # Heuristic for common patterns
        digits = re.sub(r"\D", "", candidate)
        if not digits:
            return None

        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        if 7 <= len(digits) <= 9:
            return f"+1{digits}"

        return None

    except Exception:
        logger.debug("Phone parse failed for %r", raw, exc_info=True)
        return None


def _normalize_fallback(raw: str) -> Optional[str]:
    """Digit extraction when phonenumbers not available."""
    try:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return None

        if raw.startswith("+"):
            return f"+{digits}"

        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        if len(digits) >= 7:
            return f"+{digits}"

        return None
    except Exception:
        logger.debug("Fallback normalization failed for %r", raw, exc_info=True)
        return None
