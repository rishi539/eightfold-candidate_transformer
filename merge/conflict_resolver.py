"""
Conflict resolution for multi-source candidate data.

When multiple sources provide different values for the same field, this
module decides which value to keep, from which source, and how that
conflict (or agreement) affects confidence.

All decisions are deterministic — ties on priority are broken by
lexicographic source name order.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Uses the classic dynamic-programming algorithm in O(n·m) time and O(m)
    space.
    """
    a_lower = a.lower()
    b_lower = b.lower()

    if a_lower == b_lower:
        return 0

    n, m = len(a_lower), len(b_lower)
    if n == 0:
        return m
    if m == 0:
        return n

    # Single-row DP
    prev: List[int] = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a_lower[i - 1] == b_lower[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,       # insertion
                prev[j] + 1,           # deletion
                prev[j - 1] + cost,    # substitution
            )
        prev = curr
    return prev[m]


def _values_agree(field_name: str, values: List[Any]) -> bool:
    """Return *True* when all non-``None`` *values* are considered equivalent.

    For name fields a fuzzy match (edit distance < 3) counts as agreement.
    For everything else, strict equality is required.
    """
    # Filter out None / empty
    non_empty = [v for v in values if v is not None and v != ""]
    if len(non_empty) <= 1:
        return True

    if field_name in ("full_name", "name"):
        # Pairwise fuzzy comparison
        first = str(non_empty[0])
        return all(
            _edit_distance(first, str(v)) < 3
            for v in non_empty[1:]
        )

    # Strict equality (case-insensitive for strings)
    def _norm(v: Any) -> Any:
        return v.lower() if isinstance(v, str) else v

    first_norm = _norm(non_empty[0])
    return all(_norm(v) == first_norm for v in non_empty[1:])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_conflict(
    field_name: str,
    candidates: List[Tuple[str, Any, int]],
) -> Tuple[Any, str, float]:
    """Resolve a conflict for a single field.

    Parameters
    ----------
    field_name:
        The name of the field being resolved (e.g. ``"full_name"``).
    candidates:
        A list of ``(source_name, value, priority)`` tuples, one per source
        that provides a value for the field.

    Returns
    -------
    tuple[Any, str, float]
        ``(chosen_value, chosen_source, confidence_adjustment)``

        * *chosen_value* — the winning value.
        * *chosen_source* — the source it came from.
        * *confidence_adjustment* — how this resolution should shift the
          overall confidence score:

          - All sources agree → ``+0.05``
          - Sources disagree → ``-0.10`` (highest priority wins)
          - Only one source   → ``0.0``
    """

    if not candidates:
        logger.warning("resolve_conflict called with empty candidates for %s", field_name)
        return (None, "", 0.0)

    # Filter out None / empty values
    valid: List[Tuple[str, Any, int]] = [
        (src, val, pri) for src, val, pri in candidates
        if val is not None and val != ""
    ]

    if not valid:
        logger.debug("All candidate values for '%s' are None/empty", field_name)
        # Return the first candidate's value (None) with no adjustment
        src0, val0, _ = candidates[0]
        return (val0, src0, 0.0)

    # Only one source provides the value
    if len(valid) == 1:
        src, val, _pri = valid[0]
        logger.debug("Single source '%s' for field '%s'", src, field_name)
        return (val, src, 0.0)

    # Sort deterministically: descending priority, then ascending source name
    sorted_candidates = sorted(valid, key=lambda t: (-t[2], t[0]))

    values = [val for _, val, _ in valid]
    agree = _values_agree(field_name, values)

    chosen_src, chosen_val, _chosen_pri = sorted_candidates[0]

    if agree:
        logger.debug(
            "All %d sources agree on field '%s' (value=%r, chosen_source='%s')",
            len(valid), field_name, chosen_val, chosen_src,
        )
        return (chosen_val, chosen_src, 0.05)

    # Conflict — pick highest priority
    conflicting_sources = [src for src, _, _ in valid]
    logger.info(
        "Conflict on field '%s': sources=%s — choosing '%s' (value=%r)",
        field_name, conflicting_sources, chosen_src, chosen_val,
    )
    return (chosen_val, chosen_src, -0.10)
