"""
Merge multiple RawExtractions into a single canonical CandidateProfile.

This module takes a list of ``RawExtraction`` objects that have already been
identified as belonging to the same candidate (by :mod:`merge.matcher`) and
produces one deterministic ``CandidateProfile``.

All merge rules, field-priority logic, normalisation, and deduplication
are encapsulated here.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from models.candidate import (
    CandidateProfile,
    Education,
    Experience,
    Links,
    Location,
    Provenance,
    RawExtraction,
    Skill,
)
from normalizers.country import normalize_country
from normalizers.date_normalizer import extract_year, normalize_date
from normalizers.phone import normalize_phone
from normalizers.skill import deduplicate_skills, normalize_skill

from merge.conflict_resolver import resolve_conflict
from confidence.scorer import calculate_confidence, calculate_skill_confidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source priority (higher = more trusted)
# ---------------------------------------------------------------------------

SOURCE_PRIORITY: Dict[str, int] = {
    "linkedin": 5,
    "github": 4,
    "ats_json": 3,
    "csv": 2,
    "resume_pdf": 4,
    "resume_docx": 4,
    "recruiter_notes": 1,
}

_DEFAULT_PRIORITY: int = 0  # unknown source types


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _priority(source: str) -> int:
    """Return the numeric priority for *source*."""
    return SOURCE_PRIORITY.get(source.lower().strip(), _DEFAULT_PRIORITY)


def _sort_extractions(extractions: List[RawExtraction]) -> List[RawExtraction]:
    """Return extractions sorted by descending priority, then source name.

    Deterministic — identical inputs always produce the same order.
    """
    return sorted(
        extractions,
        key=lambda e: (-_priority(getattr(e, "source_name", "") or ""),
                       (getattr(e, "source_name", "") or "").lower()),
    )


def _clean(value: Optional[str]) -> Optional[str]:
    """Strip whitespace; return *None* for empty / whitespace-only strings."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    if hasattr(obj, 'data') and isinstance(obj.data, dict):
        val = obj.data.get(attr, default)
    elif isinstance(obj, dict):
        val = obj.get(attr, default)
    else:
        val = getattr(obj, attr, default)
    if isinstance(val, str) and not val.strip():
        return default
    return val


def _normalise_phone(phone: Optional[str]) -> Optional[str]:
    cleaned = _clean(phone)
    if cleaned is None:
        return None
    try:
        result = normalize_phone(cleaned)
        return _clean(result)
    except Exception:
        return cleaned  # keep original if normalisation fails


def _normalise_date(date_str: Optional[str]) -> Optional[str]:
    """Normalise a date string to YYYY-MM format."""
    cleaned = _clean(date_str)
    if cleaned is None:
        return None
    try:
        result = normalize_date(cleaned)
        return _clean(result)
    except Exception:
        return cleaned


def _experience_key(exp: Experience) -> Tuple[str, str, str]:
    """Deduplication key for an experience entry."""
    company = (_clean(getattr(exp, "company", None)) or "").lower()
    title = (_clean(getattr(exp, "title", None)) or "").lower()
    start = (_clean(_safe_getattr(exp, "start") or _safe_getattr(exp, "start_date")) or "").lower()
    return (company, title, start)


def _education_key(edu: Education) -> Tuple[str, str]:
    """Deduplication key for an education entry."""
    institution = (_clean(getattr(edu, "institution", None)) or "").lower()
    degree = (_clean(getattr(edu, "degree", None)) or "").lower()
    return (institution, degree)


def _calculate_duration_years(experiences: List[Experience]) -> Optional[float]:
    """Estimate total years of experience from experience entries.

    Only entries with parseable start *and* end dates (or ongoing) are counted.
    Returns ``None`` when nothing can be computed.
    """
    total_months = 0.0
    counted = 0

    for exp in experiences:
        start_raw = _clean(_safe_getattr(exp, "start") or _safe_getattr(exp, "start_date"))
        end_raw = _clean(_safe_getattr(exp, "end") or _safe_getattr(exp, "end_date"))

        if start_raw is None:
            continue

        start_date = _parse_ym(start_raw)
        if start_date is None:
            continue

        if end_raw is None or end_raw.lower() in ("present", "current", "now"):
            end_date = datetime.utcnow()
        else:
            end_date = _parse_ym(end_raw)
            if end_date is None:
                continue

        diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if diff > 0:
            total_months += diff
            counted += 1

    if counted == 0:
        return None
    return round(total_months / 12.0, 1)


def _parse_ym(s: str) -> Optional[datetime]:
    """Try to parse a YYYY-MM (or YYYY) string into a datetime."""
    for fmt in ("%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _sort_key_for_date(date_str: Optional[str]) -> str:
    """Return a sort key so that most-recent-first ordering works.

    Missing dates sort to the end (empty string sorts before everything
    in descending order, so we use a far-future sentinel).
    """
    if date_str:
        return date_str
    return "0000-00"  # sorts to bottom in descending order


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_extractions(extractions: List[RawExtraction]) -> CandidateProfile:
    """Merge multiple ``RawExtraction`` objects into one ``CandidateProfile``.

    The merge is **deterministic** — identical inputs always produce the same
    output regardless of insertion or iteration order.

    Parameters
    ----------
    extractions:
        One or more ``RawExtraction`` instances that belong to the same
        candidate (as determined by :func:`merge.matcher.match_candidates`).

    Returns
    -------
    CandidateProfile
        A fully merged, normalised, and deduplicated profile.
    """

    if not extractions:
        raise ValueError("merge_extractions requires at least one extraction")

    sorted_exts = _sort_extractions(extractions)
    source_count = len({(getattr(e, "source_name", "") or "").lower() for e in extractions})
    conflict_adjustments: List[float] = []
    provenance_list: List[Provenance] = []

    # ---- 1. full_name -------------------------------------------------------
    name_candidates = [
        (getattr(e, "source_name", "unknown"), _safe_getattr(e, "full_name"), _priority(getattr(e, "source_name", "") or ""))
        for e in sorted_exts
        if _safe_getattr(e, "full_name") is not None
    ]
    full_name, name_source, name_adj = resolve_conflict("full_name", name_candidates)
    conflict_adjustments.append(name_adj)
    if full_name:
        provenance_list.append(Provenance(field_name="full_name", source=name_source, method="merge"))

    # ---- 2. emails ----------------------------------------------------------
    seen_emails: Set[str] = set()
    emails: List[str] = []
    for ext in sorted_exts:
        raw_emails = _safe_getattr(ext, "emails") or []
        if isinstance(raw_emails, str):
            raw_emails = [raw_emails]
        src = getattr(ext, "source_name", "unknown") or "unknown"
        for raw in raw_emails:
            cleaned = _clean(raw)
            if cleaned is None:
                continue
            lower = cleaned.lower()
            if lower not in seen_emails:
                seen_emails.add(lower)
                emails.append(cleaned)
                provenance_list.append(Provenance(field_name="email", source=src, method="merge"))

    # ---- 3. phones ----------------------------------------------------------
    seen_phones: Set[str] = set()
    phones: List[str] = []
    for ext in sorted_exts:
        raw_phones = _safe_getattr(ext, "phones") or []
        if isinstance(raw_phones, str):
            raw_phones = [raw_phones]
        src = getattr(ext, "source_name", "unknown") or "unknown"
        for raw in raw_phones:
            normalised = _normalise_phone(raw)
            if normalised is None:
                continue
            if normalised not in seen_phones:
                seen_phones.add(normalised)
                phones.append(normalised)
                provenance_list.append(Provenance(field_name="phone", source=src, method="merge"))

    # ---- 4. location --------------------------------------------------------
    location: Optional[Location] = None
    location_source: str = ""
    for ext in sorted_exts:
        loc = _safe_getattr(ext, "location")
        # Handle flat location from parsers
        if not loc and any([_safe_getattr(ext, "location_city"), _safe_getattr(ext, "location_region"), _safe_getattr(ext, "location_country")]):
            loc = Location(
                city=_safe_getattr(ext, "location_city"),
                region=_safe_getattr(ext, "location_region"),
                country=_safe_getattr(ext, "location_country")
            )
        if loc is not None:
            location = loc
            location_source = getattr(ext, "source_name", "unknown") or "unknown"
            # Normalise country to ISO-3166
            raw_country = loc.get("country") if isinstance(loc, dict) else _safe_getattr(loc, "country")
            if raw_country:
                try:
                    normalised_country = normalize_country(raw_country)
                    if normalised_country and hasattr(loc, "country"):
                        # Attempt to update; if frozen, create new Location
                        try:
                            loc.country = normalised_country
                        except (AttributeError, TypeError):
                            location = Location(
                                city=getattr(loc, "city", None),
                                state=getattr(loc, "state", None),
                                country=normalised_country,
                            )
                except Exception:
                    logger.debug("Country normalisation failed for '%s'", raw_country)
            provenance_list.append(Provenance(field_name="location", source=location_source, method="merge"))
            break  # first (highest priority) wins

    # ---- 5. links -----------------------------------------------------------
    merged_linkedin: Optional[str] = None
    merged_github: Optional[str] = None
    merged_portfolio: Optional[str] = None
    merged_other_links: List[str] = []
    seen_other: Set[str] = set()

    for ext in sorted_exts:
        links = _safe_getattr(ext, "links") or {}
        src = getattr(ext, "source_name", "unknown") or "unknown"

        li_val = links.get("linkedin") if isinstance(links, dict) else getattr(links, "linkedin", None)
        if not li_val:
            li_val = _safe_getattr(ext, "linkedin")
        li = _clean(li_val)
        if li and merged_linkedin is None:
            merged_linkedin = li
            provenance_list.append(Provenance(field_name="links.linkedin", source=src, method="merge"))

        gh_val = links.get("github") if isinstance(links, dict) else getattr(links, "github", None)
        if not gh_val:
            gh_val = _safe_getattr(ext, "github")
        gh = _clean(gh_val)
        if gh and merged_github is None:
            merged_github = gh
            provenance_list.append(Provenance(field_name="links.github", source=src, method="merge"))

        pf = _clean(getattr(links, "portfolio", None))
        if pf and merged_portfolio is None:
            merged_portfolio = pf
            provenance_list.append(Provenance(field_name="links.portfolio", source=src, method="merge"))

        other = getattr(links, "other", None) or []
        if isinstance(other, str):
            other = [other]
        for url in other:
            cleaned = _clean(url)
            if cleaned and cleaned.lower() not in seen_other:
                seen_other.add(cleaned.lower())
                merged_other_links.append(cleaned)

    links_obj = Links(
        linkedin=merged_linkedin,
        github=merged_github,
        portfolio=merged_portfolio,
        other=sorted(merged_other_links),
    )

    # ---- 6. headline --------------------------------------------------------
    headline_candidates = [
        (getattr(e, "source_name", "unknown"), _safe_getattr(e, "headline"), _priority(getattr(e, "source_name", "") or ""))
        for e in sorted_exts
        if _safe_getattr(e, "headline") is not None
    ]
    headline, headline_source, headline_adj = resolve_conflict("headline", headline_candidates)
    conflict_adjustments.append(headline_adj)
    if headline:
        provenance_list.append(Provenance(field_name="headline", source=headline_source, method="merge"))

    # ---- 7. skills ----------------------------------------------------------
    # Track: normalised_skill -> set of source types
    skill_sources: Dict[str, Set[str]] = defaultdict(set)
    raw_skill_names: Dict[str, str] = {}  # normalised -> best raw name

    for ext in sorted_exts:
        raw_skills = _safe_getattr(ext, "skills") or []
        if isinstance(raw_skills, str):
            raw_skills = [raw_skills]
        src = getattr(ext, "source_name", "unknown") or "unknown"
        for raw_skill in raw_skills:
            # raw_skill might be a Skill object or a string
            if isinstance(raw_skill, str):
                skill_name = raw_skill
            else:
                skill_name = getattr(raw_skill, "name", None) or str(raw_skill)

            cleaned = _clean(skill_name)
            if cleaned is None:
                continue

            try:
                normalised = normalize_skill(cleaned)
            except Exception:
                normalised = cleaned.lower()

            normalised_key = normalised.lower()
            skill_sources[normalised_key].add(src)

            # Keep the first (highest-priority) raw spelling
            if normalised_key not in raw_skill_names:
                raw_skill_names[normalised_key] = normalised

    # Deduplicate using normalizer utility if available
    all_normalised_keys = sorted(skill_sources.keys())
    try:
        deduped = deduplicate_skills(list(raw_skill_names.values()))
        # Re-index after dedup
        deduped_keys = {s.lower(): s for s in deduped}
    except Exception:
        deduped_keys = {k: raw_skill_names[k] for k in all_normalised_keys}

    skills: List[Skill] = []
    for key in sorted(deduped_keys.keys()):
        display_name = deduped_keys[key]
        sources_for_skill = skill_sources.get(key, set())
        src_list = sorted(sources_for_skill)
        conf = calculate_skill_confidence(
            skill_name=display_name,
            source_count=len(sources_for_skill),
            total_sources=source_count,
            source_types=src_list,
        )
        skills.append(Skill(
            name=display_name,
            confidence=conf,
            sources=src_list,
        ))
        for src in src_list:
            provenance_list.append(Provenance(field_name=f"skill:{display_name}", source=src, method="merge"))

    # ---- 8. experience ------------------------------------------------------
    seen_exp_keys: Set[Tuple[str, str, str]] = set()
    experience: List[Experience] = []

    for ext in sorted_exts:
        raw_exps = _safe_getattr(ext, "experience") or []
        src = getattr(ext, "source_name", "unknown") or "unknown"
        for exp in raw_exps:
            # Normalise dates
            start = _normalise_date(_safe_getattr(exp, "start") or _safe_getattr(exp, "start_date"))
            end = _normalise_date(_safe_getattr(exp, "end") or _safe_getattr(exp, "end_date"))

            key = _experience_key(exp)
            if key in seen_exp_keys:
                continue
            seen_exp_keys.add(key)

            # Build a new Experience with normalised dates
            experience.append(Experience(
                company=_safe_getattr(exp, "company"),
                title=_safe_getattr(exp, "title"),
                start=start,
                end=end,
                summary=_safe_getattr(exp, "summary") or _safe_getattr(exp, "description"),
            ))
            provenance_list.append(Provenance(
                field_name=f"experience:{_safe_getattr(exp, 'company', '')}",
                source=src,
                method="merge",
            ))

    # Sort experience by start_date descending (most recent first)
    experience.sort(key=lambda e: _sort_key_for_date(_safe_getattr(e, "start")), reverse=True)

    # ---- 9. education -------------------------------------------------------
    seen_edu_keys: Set[Tuple[str, str]] = set()
    education: List[Education] = []

    for ext in sorted_exts:
        raw_edus = _safe_getattr(ext, "education") or []
        src = getattr(ext, "source_name", "unknown") or "unknown"
        for edu in raw_edus:
            key = _education_key(edu)
            if key in seen_edu_keys:
                continue
            seen_edu_keys.add(key)

            # Extract end_year
            end_year: Optional[int] = getattr(edu, "end_year", None)
            if end_year is None:
                raw_end = _safe_getattr(edu, "end_date")
                if raw_end:
                    try:
                        end_year = extract_year(raw_end)
                    except Exception:
                        pass

            education.append(Education(
                institution=_safe_getattr(edu, "institution"),
                degree=_safe_getattr(edu, "degree"),
                field_of_study=_safe_getattr(edu, "field_of_study"),
                end_year=end_year,
            ))
            provenance_list.append(Provenance(
                field_name=f"education:{_safe_getattr(edu, 'institution', '')}",
                source=src,
                method="merge",
            ))

    # ---- 10. total_years_experience -----------------------------------------
    total_years_experience = _calculate_duration_years(experience)

    if total_years_experience is None:
        # Fallback: take from highest-priority source
        tye_candidates = [
            (getattr(e, "source_name", "unknown"),
             _safe_getattr(e, "total_years_experience"),
             _priority(getattr(e, "source_name", "") or ""))
            for e in sorted_exts
            if _safe_getattr(e, "total_years_experience") is not None
        ]
        if tye_candidates:
            total_years_experience, _, _ = resolve_conflict("total_years_experience", tye_candidates)

    # ---- 11. Build profile & compute confidence -----------------------------
    # Deduplicate and sort provenance deterministically
    prov_dedup: Dict[Tuple[str, str], Provenance] = {}
    for p in provenance_list:
        key = (p.field_name, p.source)
        if key not in prov_dedup:
            prov_dedup[key] = p
    provenance_sorted = sorted(prov_dedup.values(), key=lambda p: (p.field_name, p.source))

    profile = CandidateProfile(
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links_obj,
        headline=headline,
        skills=skills,
        experience=experience,
        education=education,
        total_years_experience=total_years_experience,
        provenance=provenance_sorted,
        
        overall_confidence=0.0,  # placeholder, calculated next
    )

    # Calculate overall confidence
    profile.overall_confidence = calculate_confidence(
        profile=profile,
        source_count=source_count,
        conflict_adjustments=conflict_adjustments,
    )

    logger.info(
        "Merged %d extractions → profile for '%s' (confidence=%.3f)",
        len(extractions),
        full_name,
        profile.overall_confidence,
    )

    return profile
