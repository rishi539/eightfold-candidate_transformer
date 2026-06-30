"""ATS JSON parser handling diverse field naming conventions across platforms."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from models.candidate import RawExtraction
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# Field variant mappings (case-insensitive, first match wins)
_NAME_FIELDS = [
    "applicant_name", "candidate_name", "full_name", "fullname", "name",
]
_FIRST_NAME_FIELDS = ["first_name", "firstname", "given_name", "fname"]
_LAST_NAME_FIELDS = [
    "last_name", "lastname", "surname", "family_name", "lname",
]
_EMAIL_FIELDS = [
    "email_address", "contact_email", "email", "emails", "e_mail",
]
_PHONE_FIELDS = [
    "phone_number", "mobile", "contact_phone", "phone", "phones",
    "telephone", "cell",
]
_COMPANY_FIELDS = [
    "current_employer", "organization", "organisation", "company",
    "employer", "current_company",
]
_TITLE_FIELDS = [
    "job_title", "position", "role", "designation", "title", "current_title",
]
_SKILLS_FIELDS = [
    "skill_set", "competencies", "technologies", "skills", "tech_stack",
]
_EXPERIENCE_FIELDS = [
    "work_history", "employment", "experience", "positions",
    "professional_experience", "career_history",
]
_EDUCATION_FIELDS = [
    "academic", "education", "qualifications", "degrees",
    "academic_background",
]
_CITY_FIELDS = ["city", "location_city"]
_LOCATION_FIELDS = ["location", "address", "loc"]
_REGION_FIELDS = ["state", "region", "province", "location_state"]
_COUNTRY_FIELDS = ["country", "location_country"]
_LINKEDIN_FIELDS = ["linkedin", "linkedin_url", "linkedin_profile"]
_GITHUB_FIELDS = ["github", "github_url", "github_profile"]


class ATSParser(BaseParser):
    """Parse ATS JSON into RawExtraction records."""

    def can_handle(self, source_path: str) -> bool:
        """Return True for .json files."""
        return os.path.splitext(source_path)[1].lower() == ".json"

    def parse(self, source_path: str) -> list[RawExtraction]:
        """Extract candidates from JSON (handles single obj or array)."""
        raw_text = self._read_file(source_path)
        if raw_text is None:
            return [
                RawExtraction(
                    source_name="ats_json",
                    source_file=source_path,
                    is_valid=False,
                    warnings=[f"Could not read file: {source_path}"],
                )
            ]

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON in %s: %s", source_path, exc)
            return [
                RawExtraction(
                    source_name="ats_json",
                    source_file=source_path,
                    is_valid=False,
                    warnings=[f"JSON decode error: {exc}"],
                )
            ]

        # Handle both single objects and arrays
        records: List[Dict[str, Any]]
        if isinstance(payload, dict):
            candidates_key = self._find_candidates_key(payload)
            if candidates_key and isinstance(payload[candidates_key], list):
                records = payload[candidates_key]
            else:
                records = [payload]
        elif isinstance(payload, list):
            records = payload
        else:
            return [
                RawExtraction(
                    source_name="ats_json",
                    source_file=source_path,
                    is_valid=False,
                    warnings=[f"Unexpected JSON type: {type(payload).__name__}"],
                )
            ]

        extractions: list[RawExtraction] = []
        for idx, record in enumerate(records):
            if not isinstance(record, dict):
                extractions.append(
                    RawExtraction(
                        source_name="ats_json",
                        source_file=source_path,
                        is_valid=False,
                        warnings=[f"Record {idx}: not a dict"],
                    )
                )
                continue
            try:
                ext = self._parse_record(record, source_path, idx)
                extractions.append(ext)
            except Exception as exc:
                logger.warning("Record %d failed: %s", idx, exc)
                extractions.append(
                    RawExtraction(
                        source_name="ats_json",
                        source_file=source_path,
                        is_valid=False,
                        warnings=[f"Record {idx}: {exc}"],
                    )
                )

        if not extractions:
            extractions.append(
                RawExtraction(
                    source_name="ats_json",
                    source_file=source_path,
                    is_valid=False,
                    warnings=["JSON contained no candidate records."],
                )
            )

        return extractions

    @staticmethod
    def _read_file(path: str) -> Optional[str]:
        """Read file as UTF-8."""
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                return fh.read()
        except OSError as exc:
            logger.error("Cannot open %s: %s", path, exc)
            return None

    @staticmethod
    def _find_candidates_key(payload: Dict[str, Any]) -> Optional[str]:
        """Find array wrapper key (candidates, applicants, etc.)."""
        known_keys = {"candidates", "applicants", "data", "records", "results", "items", "entries"}
        lower_map = {k.lower(): k for k in payload}
        for key in known_keys:
            if key in lower_map:
                return lower_map[key]
        return None

    @classmethod
    def _resolve(cls, record: Dict[str, Any], field_variants: List[str]) -> Any:
        """Return first matching field variant (case-insensitive), or None."""
        lower_map = {k.lower(): k for k in record}
        for variant in field_variants:
            actual = lower_map.get(variant.lower())
            if actual is not None and record[actual] is not None:
                return record[actual]
        return None

    @classmethod
    def _resolve_str(cls, record: Dict[str, Any], field_variants: List[str]) -> Optional[str]:
        """Resolve to stripped string or None."""
        val = cls._resolve(record, field_variants)
        if val is None:
            return None
        text = str(val).strip()
        return text if text else None

    @classmethod
    def _resolve_list(
        cls,
        record: Dict[str, Any],
        field_variants: List[str],
    ) -> List[str]:
        """Resolve to a list of strings.

        If string: split on comma/semicolon. If list: stringify each item.
        """
        val = cls._resolve(record, field_variants)
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        text = str(val).strip()
        if not text:
            return []
        return [p.strip() for p in re.split(r"[;,]", text) if p.strip()]

    @classmethod
    def _parse_record(cls, record: Dict[str, Any], source_path: str, idx: int) -> RawExtraction:
        """Extract fields from single ATS record."""
        warnings: List[str] = []

        # Name (try full_name, then first + last)
        full_name = cls._resolve_str(record, _NAME_FIELDS)
        if full_name is None:
            first = cls._resolve_str(record, _FIRST_NAME_FIELDS)
            last = cls._resolve_str(record, _LAST_NAME_FIELDS)
            if first or last:
                full_name = " ".join(filter(None, [first, last]))

        # Contact info
        emails = cls._resolve_list(record, _EMAIL_FIELDS)
        phones = cls._resolve_list(record, _PHONE_FIELDS)

        # Professional
        company = cls._resolve_str(record, _COMPANY_FIELDS)
        title = cls._resolve_str(record, _TITLE_FIELDS)
        skills = cls._resolve_list(record, _SKILLS_FIELDS)

        # Experience & education
        experience = cls._normalise_experience(cls._resolve(record, _EXPERIENCE_FIELDS))
        education = cls._normalise_education(cls._resolve(record, _EDUCATION_FIELDS))

        # Location (try explicit fields, fallback to generic)
        city = cls._resolve_str(record, _CITY_FIELDS)
        region = cls._resolve_str(record, _REGION_FIELDS)
        country = cls._resolve_str(record, _COUNTRY_FIELDS)

        if not any([city, region, country]):
            loc_val = cls._resolve(record, _LOCATION_FIELDS)
            if isinstance(loc_val, dict):
                lower_loc = {k.lower(): k for k in loc_val}
                for v in _CITY_FIELDS:
                    if v in lower_loc and loc_val[lower_loc[v]] is not None:
                        city = str(loc_val[lower_loc[v]]).strip()
                        break
                for v in _REGION_FIELDS:
                    if v in lower_loc and loc_val[lower_loc[v]] is not None:
                        region = str(loc_val[lower_loc[v]]).strip()
                        break
                for v in _COUNTRY_FIELDS:
                    if v in lower_loc and loc_val[lower_loc[v]] is not None:
                        country = str(loc_val[lower_loc[v]]).strip()
                        break
            elif loc_val is not None:
                loc_str = str(loc_val).strip()
                if loc_str:
                    parts = [p.strip() for p in loc_str.split(",") if p.strip()]
                    if len(parts) >= 3:
                        city, region, country = parts[0], parts[1], parts[2]
                    elif len(parts) == 2:
                        city, region = parts[0], parts[1]
                    elif len(parts) == 1:
                        city = parts[0]

        # Social & validation
        linkedin = cls._resolve_str(record, _LINKEDIN_FIELDS)
        github = cls._resolve_str(record, _GITHUB_FIELDS)

        if not full_name and not emails:
            warnings.append(f"Record {idx}: missing name and email")

        data: Dict[str, Any] = {
            "full_name": full_name,
            "emails": emails,
            "phones": phones,
            "company": company,
            "title": title,
            "skills": skills,
            "experience": experience,
            "education": education,
            "location_city": city,
            "location_region": region,
            "location_country": country,
            "linkedin": linkedin,
            "github": github,
        }

        return RawExtraction(
            source_name="ats_json",
            source_file=source_path,
            data=data,
            warnings=warnings,
            is_valid=True,
        )

    @staticmethod
    def _normalise_experience(raw: Any) -> List[Dict[str, Any]]:
        """Normalize experience to list of dicts. Handles None, strings, lists."""
        if raw is None:
            return []
        if isinstance(raw, str):
            return [{"summary": line.strip()} for line in raw.splitlines() if line.strip()]
        if not isinstance(raw, list):
            return [{"summary": str(raw)}]

        entries: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                entry: Dict[str, Any] = {}
                lower_map = {k.lower(): k for k in item}
                for canonical, variants in {
                    "company": ["company", "employer", "organization", "organisation", "company_name"],
                    "title": ["title", "job_title", "position", "role", "designation"],
                    "start_date": ["start_date", "start", "from", "date_from"],
                    "end_date": ["end_date", "end", "to", "date_to"],
                    "summary": ["summary", "description", "responsibilities",
                        "details", "duties",
                    ],
                }.items():
                    for v in variants:
                        actual = lower_map.get(v)
                        if actual is not None and item[actual] is not None:
                            val = item[actual]
                            if isinstance(val, list):
                                entry[canonical] = "\n".join(
                                    str(x) for x in val
                                )
                            else:
                                entry[canonical] = str(val).strip()
                            break
                    else:
                        entry[canonical] = None
                entries.append(entry)
            elif isinstance(item, str) and item.strip():
                entries.append({"summary": item.strip()})
            # Silently skip non-string, non-dict items
        return entries

    @staticmethod
    def _normalise_education(raw: Any) -> List[Dict[str, Any]]:
        """Normalise education data into a list of dicts.

        Similar flexibility as ``_normalise_experience``.
        """
        if raw is None:
            return []
        if isinstance(raw, str):
            return [
                {"summary": line.strip()}
                for line in raw.splitlines()
                if line.strip()
            ]
        if not isinstance(raw, list):
            return [{"summary": str(raw)}]

        entries: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                entry: Dict[str, Any] = {}
                lower_map = {k.lower(): k for k in item}
                for canonical, variants in {
                    "institution": [
                        "institution", "school", "university", "college",
                        "institute", "school_name",
                    ],
                    "degree": ["degree", "qualification", "diploma", "cert"],
                    "field_of_study": [
                        "field_of_study", "field", "major", "subject",
                        "specialization", "concentration",
                    ],
                    "year": [
                        "year", "graduation_year", "end_year",
                        "completion_year",
                    ],
                }.items():
                    for v in variants:
                        actual = lower_map.get(v)
                        if actual is not None and item[actual] is not None:
                            entry[canonical] = str(item[actual]).strip()
                            break
                    else:
                        entry[canonical] = None
                entries.append(entry)
            elif isinstance(item, str) and item.strip():
                entries.append({"summary": item.strip()})
        return entries
