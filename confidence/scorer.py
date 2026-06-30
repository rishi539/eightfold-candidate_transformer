"""Confidence scoring for candidate profiles and individual skills."""

from __future__ import annotations

import logging
from typing import List

from models.candidate import CandidateProfile

logger = logging.getLogger(__name__)

# Scoring constants
_BASE_SCORE: float = 0.50
_PER_SOURCE_BONUS: float = 0.10
_MAX_SOURCE_BONUS_SOURCES: int = 4

_FIELD_COMPLETENESS_BONUS: float = 0.02
_REQUIRED_FIELDS: List[str] = [
    "full_name", "emails", "phones", "experience", "skills", "education",
]
_CRITICAL_FIELDS: List[str] = ["full_name", "emails"]
_CRITICAL_MISSING_PENALTY: float = 0.05
_NAME_AGREEMENT_BONUS: float = 0.05

# Skill thresholds
_SKILL_CONF_1_SOURCE: float = 0.60
_SKILL_CONF_2_SOURCES: float = 0.80
_SKILL_CONF_3_PLUS: float = 0.95
_SKILL_TRUSTED_SOURCE_BONUS: float = 0.05
_TRUSTED_SKILL_SOURCES = frozenset({"resume_pdf", "resume_docx", "linkedin"})


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to range [lo, hi]."""
    return max(lo, min(hi, value))


def _field_is_present(profile: CandidateProfile, field: str) -> bool:
    """Check if a field has a non-empty value."""
    value = getattr(profile, field, None)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value) > 0
    return True


def calculate_confidence(
    profile: CandidateProfile,
    source_count: int,
    conflict_adjustments: List[float],
) -> float:
    """Calculate overall confidence score (0-1).
    
    Factors: base 0.5 + per-source bonus + field completeness + conflict adjustments.
    """
    score = _BASE_SCORE

    # Bonus for multiple sources
    effective_sources = min(source_count, _MAX_SOURCE_BONUS_SOURCES)
    score += effective_sources * _PER_SOURCE_BONUS

    # Bonus for having required fields
    for field in _REQUIRED_FIELDS:
        if _field_is_present(profile, field):
            score += _FIELD_COMPLETENESS_BONUS

    # Apply conflict-based adjustments
    total_adj = sum(conflict_adjustments) if conflict_adjustments else 0.0
    score += total_adj

    # Bonus if multiple sources agree on name
    if source_count >= 2 and _field_is_present(profile, "full_name"):
        score += _NAME_AGREEMENT_BONUS

    # Penalty for missing critical fields
    for field in _CRITICAL_FIELDS:
        if not _field_is_present(profile, field):
            score -= _CRITICAL_MISSING_PENALTY

    final = _clamp(score)
    logger.info("Confidence for %r: %.3f", getattr(profile, "full_name", None), final)
    return final


def calculate_skill_confidence(
    skill_name: str,
    source_count: int,
    total_sources: int,
    source_types: List[str] | None = None,
) -> float:
    """Calculate skill confidence based on how many sources mention it.
    
    1 source=60%, 2 sources=80%, 3+=95%. +5% if from resume or LinkedIn.
    """
    if source_count <= 0:
        return 0.0

    if source_count == 1:
        base = _SKILL_CONF_1_SOURCE
    elif source_count == 2:
        base = _SKILL_CONF_2_SOURCES
    else:
        base = _SKILL_CONF_3_PLUS

    # Bonus for trusted sources
    bonus = 0.0
    if source_types and _TRUSTED_SKILL_SOURCES.intersection(source_types):
        bonus = _SKILL_TRUSTED_SOURCE_BONUS

    return _clamp(base + bonus)
