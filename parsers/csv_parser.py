"""
CSV parser for recruiter spreadsheet exports.

Handles a variety of column naming conventions, encoding issues, BOM
markers, and malformed rows.  Produces one :class:`RawExtraction` per
non-empty data row.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from models.candidate import RawExtraction
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flexible column-name mappings
# ---------------------------------------------------------------------------
# Each canonical field maps to an ordered list of possible header variants
# (all lower-cased for comparison).
_COLUMN_MAP: Dict[str, List[str]] = {
    "full_name": [
        "name", "full_name", "full name", "candidate_name", "candidate name",
        "applicant_name", "applicant name",
    ],
    "first_name": [
        "first_name", "first name", "firstname", "given_name", "given name",
    ],
    "last_name": [
        "last_name", "last name", "lastname", "surname", "family_name",
        "family name",
    ],
    "email": [
        "email", "emails", "email_address", "email address",
        "contact_email", "contact email", "e-mail",
    ],
    "phone": [
        "phone", "phones", "phone_number", "phone number",
        "mobile", "telephone", "contact_phone", "contact phone", "cell",
    ],
    "company": [
        "company", "current_company", "current company", "employer",
        "current_employer", "current employer", "organization", "organisation",
    ],
    "title": [
        "title", "job_title", "job title", "position", "role",
        "designation", "current_title", "current title",
    ],
    "location_city": [
        "city", "location_city", "location city",
    ],
    "location_region": [
        "state", "region", "province", "location_state", "location state",
        "location_region", "location region",
    ],
    "location_country": [
        "country", "location_country", "location country",
    ],
    "location": [
        "location", "address", "loc",
    ],
    "skills": [
        "skills", "skill_set", "skill set", "competencies",
        "technologies", "tech_stack", "tech stack",
    ],
    "linkedin": [
        "linkedin", "linkedin_url", "linkedin url", "linkedin_profile",
        "linkedin profile",
    ],
    "github": [
        "github", "github_url", "github url", "github_profile",
        "github profile",
    ],
}

# Encodings to try, in order of preference.
_ENCODINGS: Sequence[str] = ("utf-8-sig", "utf-8", "latin-1", "cp1252")


class CSVParser(BaseParser):
    """Parse recruiter CSV exports into :class:`RawExtraction` records."""

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def can_handle(self, source_path: str) -> bool:
        """Return ``True`` for paths ending in ``.csv`` (case-insensitive)."""
        return os.path.splitext(source_path)[1].lower() == ".csv"

    def parse(self, source_path: str) -> list[RawExtraction]:
        """Read *source_path* and return one extraction per data row.

        The method never raises – errors are captured as warnings inside
        the returned :class:`RawExtraction` objects or logged and skipped.
        """
        extractions: list[RawExtraction] = []

        text = self._read_file(source_path)
        if text is None:
            extraction = RawExtraction(
                source_name="csv",
                source_file=source_path,
                is_valid=False,
                warnings=[f"Could not read file with any supported encoding: {source_path}"],
            )
            extractions.append(extraction)
            return extractions

        try:
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames is None:
                return [
                    RawExtraction(
                        source_name="csv",
                        source_file=source_path,
                        is_valid=False,
                        warnings=["CSV file appears to be empty or has no header row."],
                    )
                ]

            col_lookup = self._build_column_lookup(
                [str(f) for f in reader.fieldnames]
            )

            for row_num, row in enumerate(reader, start=2):  # 1-indexed header = row 1
                try:
                    extraction = self._parse_row(row, col_lookup, source_path, row_num)
                    if extraction is not None:
                        extractions.append(extraction)
                except Exception as exc:  # pragma: no cover – defensive
                    logger.warning("Row %d skipped due to error: %s", row_num, exc)
                    extractions.append(
                        RawExtraction(
                            source_name="csv",
                            source_file=source_path,
                            is_valid=False,
                            warnings=[f"Row {row_num}: unexpected error – {exc}"],
                        )
                    )

        except csv.Error as exc:
            logger.error("CSV parsing error in %s: %s", source_path, exc)
            extractions.append(
                RawExtraction(
                    source_name="csv",
                    source_file=source_path,
                    is_valid=False,
                    warnings=[f"CSV parsing error: {exc}"],
                )
            )

        return extractions

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _read_file(path: str) -> Optional[str]:
        """Try reading *path* with multiple encodings, return text or ``None``."""
        for enc in _ENCODINGS:
            try:
                with open(path, "r", encoding=enc) as fh:
                    return fh.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except OSError as exc:
                logger.error("Cannot open %s: %s", path, exc)
                return None
        return None

    @staticmethod
    def _build_column_lookup(headers: List[str]) -> Dict[str, Optional[str]]:
        """Map each canonical field name to the actual CSV header (or ``None``).

        Returns a dict like ``{'full_name': 'Full Name', 'email': 'Email', …}``.
        """
        normalised = {h.strip().lower(): h for h in headers}
        lookup: Dict[str, Optional[str]] = {}
        for canonical, variants in _COLUMN_MAP.items():
            lookup[canonical] = None
            for variant in variants:
                if variant in normalised:
                    lookup[canonical] = normalised[variant]
                    break
        return lookup

    @classmethod
    def _clean(cls, value: Optional[str]) -> Optional[str]:
        """Strip whitespace/quotes and convert empty strings to ``None``."""
        if value is None:
            return None
        cleaned = value.strip().strip('"').strip("'").strip()
        return cleaned if cleaned else None

    @classmethod
    def _split_multi(cls, value: Optional[str]) -> List[str]:
        """Split a value on ``;`` or ``,`` and return non-empty parts."""
        if not value:
            return []
        # Split on semicolons or commas
        parts = re.split(r"[;,]", value)
        return [p.strip() for p in parts if p.strip()]

    def _get(
        self,
        row: Dict[str, Any],
        col_lookup: Dict[str, Optional[str]],
        canonical: str,
    ) -> Optional[str]:
        """Get a cleaned value from *row* using the column lookup."""
        header = col_lookup.get(canonical)
        if header is None:
            return None
        raw = row.get(header)
        return self._clean(str(raw)) if raw is not None else None

    def _parse_row(
        self,
        row: Dict[str, Any],
        col_lookup: Dict[str, Optional[str]],
        source_path: str,
        row_num: int,
    ) -> Optional[RawExtraction]:
        """Convert a single CSV *row* into a :class:`RawExtraction`.

        Returns ``None`` if the row is entirely empty.
        """
        warnings: List[str] = []

        # Skip rows where every value is empty / whitespace
        if all(
            not self._clean(str(v)) for v in row.values() if v is not None
        ):
            return None

        # --- Name -----------------------------------------------------------
        full_name = self._get(row, col_lookup, "full_name")
        if full_name is None:
            first = self._get(row, col_lookup, "first_name")
            last = self._get(row, col_lookup, "last_name")
            if first or last:
                full_name = " ".join(filter(None, [first, last]))

        # --- Emails ----------------------------------------------------------
        raw_email = self._get(row, col_lookup, "email")
        emails = self._split_multi(raw_email)

        # --- Phones ----------------------------------------------------------
        raw_phone = self._get(row, col_lookup, "phone")
        phones = self._split_multi(raw_phone)

        # --- Company / Title -------------------------------------------------
        company = self._get(row, col_lookup, "company")
        title = self._get(row, col_lookup, "title")

        # --- Location --------------------------------------------------------
        location_city = self._get(row, col_lookup, "location_city")
        location_region = self._get(row, col_lookup, "location_region")
        location_country = self._get(row, col_lookup, "location_country")

        # Fallback: try a generic "location" column
        if not any([location_city, location_region, location_country]):
            generic_loc = self._get(row, col_lookup, "location")
            if generic_loc:
                # Simple heuristic: split on comma
                parts = [p.strip() for p in generic_loc.split(",") if p.strip()]
                if len(parts) >= 3:
                    location_city, location_region, location_country = (
                        parts[0],
                        parts[1],
                        parts[2],
                    )
                elif len(parts) == 2:
                    location_city, location_region = parts[0], parts[1]
                elif len(parts) == 1:
                    location_city = parts[0]

        # --- Skills ----------------------------------------------------------
        raw_skills = self._get(row, col_lookup, "skills")
        skills: List[str] = []
        if raw_skills:
            skills = [
                s.strip()
                for s in re.split(r"[;,|]", raw_skills)
                if s.strip()
            ]

        # --- Social links ----------------------------------------------------
        linkedin = self._get(row, col_lookup, "linkedin")
        github = self._get(row, col_lookup, "github")

        # --- Validation warnings --------------------------------------------
        if not full_name and not emails:
            warnings.append(
                f"Row {row_num}: missing both name and email – record may "
                "be unusable."
            )

        data: Dict[str, Any] = {
            "full_name": full_name,
            "emails": emails,
            "phones": phones,
            "company": company,
            "title": title,
            "location_city": location_city,
            "location_region": location_region,
            "location_country": location_country,
            "skills": skills,
            "linkedin": linkedin,
            "github": github,
        }

        return RawExtraction(
            source_name="csv",
            source_file=source_path,
            data=data,
            warnings=warnings,
            is_valid=True,
        )
