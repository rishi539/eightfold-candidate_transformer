"""
PDF parser for resume / CV documents.

Uses **pdfplumber** to extract text and applies regex heuristics to pull
out structured candidate information such as contact details, skills,
experience, and education.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from models.candidate import RawExtraction
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

_PHONE_RE = re.compile(
    r"""
    (?:
        (?:\+?\d{1,3}[\s\-.]?)?       # optional country code
        (?:\(?\d{2,4}\)?[\s\-.]?)?     # optional area code
        \d{3,4}[\s\-.]?\d{3,4}        # main number
    )
    """,
    re.VERBOSE,
)

_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%.]+/?",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-%.]+/?",
    re.IGNORECASE,
)

# Section header patterns (case-insensitive).
_SKILLS_HEADERS = re.compile(
    r"^\s*(?:skills|technical\s+skills|technologies|core\s+competencies"
    r"|areas?\s+of\s+expertise)\s*:?\s*$",
    re.IGNORECASE,
)

_EXPERIENCE_HEADERS = re.compile(
    r"^\s*(?:experience|work\s+experience|employment(?:\s+history)?"
    r"|professional\s+experience|career\s+history|history|work)\s*:?\s*$",
    re.IGNORECASE,
)

_EDUCATION_HEADERS = re.compile(
    r"^\s*(?:education|academic(?:\s+background)?|qualifications"
    r"|degrees?|scholastic)\s*:?\s*$",
    re.IGNORECASE,
)

# Generic section header — used to detect the *end* of a section.
_ANY_SECTION_HEADER = re.compile(
    r"^\s*(?:skills|technical\s+skills|technologies|core\s+competencies"
    r"|areas?\s+of\s+expertise|experience|work\s+experience"
    r"|employment(?:\s+history)?|professional\s+experience|career\s+history|history|work"
    r"|education|academic(?:\s+background)?|qualifications|degrees?|scholastic"
    r"|projects?|certifications?|awards?|publications?"
    r"|interests|hobbies|references?|summary|objective"
    r"|profile|about(?:\s+me)?|personal\s+information"
    r"|languages?|volunteer(?:ing)?|achievements?)\s*:?\s*$",
    re.IGNORECASE,
)

# Date-range patterns.
_DATE_RANGE_RE = re.compile(
    r"""
    (?P<start>
        (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?
        |Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?
        |Dec(?:ember)?)
        \s+\d{4}
      | \d{4}
    )
    \s*[\-–—to]+\s*
    (?P<end>
        (?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?
        |Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?
        |Dec(?:ember)?)
        \s+\d{4}
      | \d{4}
      | [Pp]resent
      | [Cc]urrent
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Location heuristic: "City, ST", "City, State", "City, State, Country"
_LOCATION_RE = re.compile(
    r"(?P<city>[A-Z][a-zA-Z\s]+),\s*(?P<region>[A-Z]{2}|[A-Za-z\s]+)"
    r"(?:,\s*(?P<country>[A-Za-z\s]+))?",
)


class PDFParser(BaseParser):
    """Extract candidate data from a resume / CV stored as a PDF."""

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def can_handle(self, source_path: str) -> bool:
        """Return ``True`` for ``.pdf`` files."""
        return os.path.splitext(source_path)[1].lower() == ".pdf"

    def parse(self, source_path: str) -> list[RawExtraction]:
        """Parse a PDF resume and return a single-element list.

        If the PDF cannot be read at all, a single invalid
        :class:`RawExtraction` with an appropriate warning is returned.
        """
        text = self._extract_text(source_path)
        if text is None:
            return [
                RawExtraction(
                    source_name="resume_pdf",
                    source_file=source_path,
                    is_valid=False,
                    warnings=["Failed to extract text from PDF."],
                )
            ]

        warnings: List[str] = []
        if not text.strip():
            warnings.append(
                "PDF contains no extractable text (possibly a scanned image)."
            )
            return [
                RawExtraction(
                    source_name="resume_pdf",
                    source_file=source_path,
                    data={},
                    warnings=warnings,
                    is_valid=False,
                )
            ]

        lines = text.splitlines()

        # --- Contact info ---------------------------------------------------
        emails = _EMAIL_RE.findall(text)
        phones = self._extract_phones(text)
        linkedin = self._first_match(_LINKEDIN_RE, text)
        github = self._first_match(_GITHUB_RE, text)

        # --- Name (heuristic) -----------------------------------------------
        name = self._extract_name(lines, emails)

        # --- Headline -------------------------------------------------------
        headline = self._extract_headline(lines, emails)

        # --- Sections -------------------------------------------------------
        skills = self._extract_skills(lines)
        experience = self._extract_experience(lines)
        education = self._extract_education(lines)

        # --- Location -------------------------------------------------------
        city, region, country = self._extract_location(text)

        data: Dict[str, Any] = {
            "full_name": name,
            "headline": headline,
            "emails": list(dict.fromkeys(emails)),  # deduplicate, keep order
            "phones": list(dict.fromkeys(phones)),
            "linkedin": linkedin,
            "github": github,
            "skills": skills,
            "experience": experience,
            "education": education,
            "location_city": city,
            "location_region": region,
            "location_country": country,
        }

        return [
            RawExtraction(
                source_name="resume_pdf",
                source_file=source_path,
                data=data,
                warnings=warnings,
                is_valid=True,
            )
        ]

    # ------------------------------------------------------------------ #
    # Text extraction
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text(path: str) -> Optional[str]:
        """Use *pdfplumber* to pull text from every page.

        Returns ``None`` on any unrecoverable error (missing file,
        encrypted PDF, dependency issues, etc.).
        """
        try:
            import pdfplumber  # type: ignore[import-untyped]
        except ImportError:
            logger.error(
                "pdfplumber is not installed. "
                "Install it with: pip install pdfplumber"
            )
            return None

        try:
            pages_text: List[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
            return "\n".join(pages_text)
        except Exception as exc:
            logger.warning("Could not read PDF %s: %s", path, exc)
            return None

    # ------------------------------------------------------------------ #
    # Field extraction helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
        """Return the first regex match or ``None``."""
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _extract_phones(text: str) -> List[str]:
        """Extract phone-number candidates and do basic validation."""
        raw = _PHONE_RE.findall(text)
        phones: List[str] = []
        for phone in raw:
            digits = re.sub(r"\D", "", phone)
            # Discard matches that are too short (likely years) or too long
            if 7 <= len(digits) <= 15:
                phones.append(phone.strip())
        return phones

    @staticmethod
    def _extract_name(lines: List[str], emails: List[str]) -> Optional[str]:
        """Heuristic: the name is the first substantial non-contact line."""
        email_set = set(emails)
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Skip if the line is just an email or phone
            if stripped in email_set:
                continue
            if _EMAIL_RE.fullmatch(stripped):
                continue
            if _PHONE_RE.fullmatch(stripped):
                continue
            # Skip lines that look like addresses or URLs
            if stripped.startswith("http") or "@" in stripped:
                continue
            # Skip common document headers
            if stripped.lower() in {"resume", "cv", "curriculum vitae", "profile"}:
                continue
            # Skip divider artifacts
            if len(set(stripped.replace(" ", ""))) <= 1:
                continue
            # A name line is typically short (< 60 chars) and mostly letters
            if len(stripped) > 60:
                continue
            letter_ratio = sum(c.isalpha() or c.isspace() for c in stripped) / max(len(stripped), 1)
            if letter_ratio > 0.7:
                return stripped
        return None

    @staticmethod
    def _extract_headline(
        lines: List[str], emails: List[str]
    ) -> Optional[str]:
        """Return the line immediately following the detected name line.

        Skips contact-info lines (email, phone, URL).
        """
        email_set = set(emails)
        found_name = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if not found_name:
                # same heuristic as _extract_name to locate the name line
                if stripped in email_set or _EMAIL_RE.fullmatch(stripped):
                    continue
                if stripped.startswith("http") or "@" in stripped:
                    continue
                if stripped.lower() in {"resume", "cv", "curriculum vitae", "profile"}:
                    continue
                if len(set(stripped.replace(" ", ""))) <= 1:
                    continue
                if len(stripped) > 60:
                    continue
                letter_ratio = sum(
                    c.isalpha() or c.isspace() for c in stripped
                ) / max(len(stripped), 1)
                if letter_ratio > 0.7:
                    found_name = True
                    continue
            else:
                # Next non-empty line after name
                if _EMAIL_RE.fullmatch(stripped):
                    continue
                if _PHONE_RE.fullmatch(stripped):
                    continue
                if stripped.startswith("http") or "@" in stripped:
                    continue
                # Skip divider artifacts like 'nnnnnnn'
                if len(set(stripped.replace(" ", ""))) <= 1:
                    continue
                if _ANY_SECTION_HEADER.match(stripped):
                    return None  # ran into a section header – no headline
                return stripped
        return None

    # ------------------------------------------------------------------ #
    # Section extraction
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_section_lines(
        cls,
        lines: List[str],
        header_re: re.Pattern[str],
    ) -> List[str]:
        """Return lines belonging to a specific section.

        Collects lines between a matching *header_re* and the next section
        header (detected by ``_ANY_SECTION_HEADER``).
        """
        in_section = False
        section_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if header_re.match(stripped):
                in_section = True
                continue
            if in_section:
                if _ANY_SECTION_HEADER.match(stripped) and not header_re.match(stripped):
                    break
                section_lines.append(line)
        return section_lines

    @classmethod
    def _extract_skills(cls, lines: List[str]) -> List[str]:
        """Parse the skills section into a flat list of skill strings."""
        section = cls._get_section_lines(lines, _SKILLS_HEADERS)
        skills: List[str] = []
        for line in section:
            stripped = line.strip()
            if not stripped:
                continue
            # Split on common delimiters: comma, pipe, bullet, semicolon
            parts = re.split(r"[,|;•●▪◦\-–—]\s*", stripped)
            for part in parts:
                cleaned = part.strip().strip("•●▪◦-–— \t")
                if cleaned and len(cleaned) < 80:
                    skills.append(cleaned)
        return skills

    @classmethod
    def _extract_experience(cls, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse the experience section into structured entries.

        Each entry is a dict with keys: ``company``, ``title``,
        ``date_range``, ``start_date``, ``end_date``, ``summary``.
        """
        section = cls._get_section_lines(lines, _EXPERIENCE_HEADERS)
        
        # Fallback for creative resumes with no recognized header
        if not section:
            collecting = False
            for line in lines:
                if not collecting and _DATE_RANGE_RE.search(line):
                    collecting = True
                if collecting:
                    if _ANY_SECTION_HEADER.match(line):
                        break
                    section.append(line)

        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        summary_lines: List[str] = []

        for line in section:
            stripped = line.strip()
            if not stripped:
                continue

            # Check for a date range — signals a new entry boundary.
            date_match = _DATE_RANGE_RE.search(stripped)
            if date_match:
                # Save previous entry
                if current is not None:
                    current["summary"] = "\n".join(summary_lines).strip() or None
                    entries.append(current)

                # Start new entry
                start_date = date_match.group("start")
                end_date = date_match.group("end")
                non_date = _DATE_RANGE_RE.sub("", stripped).strip().strip("|–—-,").strip()

                company: Optional[str] = None
                title: Optional[str] = None

                # Heuristic: split "Title at Company" or "Title, Company"
                for sep in (" at ", " @ ", " – ", " - ", ", "):
                    if sep in non_date:
                        parts = non_date.split(sep, 1)
                        title, company = parts[0].strip(), parts[1].strip()
                        break
                else:
                    # If no separator found, treat the whole thing as a title
                    title = non_date if non_date else None

                current = {
                    "company": company,
                    "title": title,
                    "date_range": f"{start_date} - {end_date}",
                    "start_date": start_date,
                    "end_date": end_date,
                    "summary": None,
                }
                summary_lines = []
            elif current is not None:
                # Accumulate summary / bullet lines
                summary_lines.append(stripped)

        # Don't forget the last entry
        if current is not None:
            current["summary"] = "\n".join(summary_lines).strip() or None
            entries.append(current)

        return entries

    @classmethod
    def _extract_education(cls, lines: List[str]) -> List[Dict[str, Any]]:
        """Parse the education section.

        Each entry is a dict with keys: ``institution``, ``degree``,
        ``field_of_study``, ``year``.
        """
        section = cls._get_section_lines(lines, _EDUCATION_HEADERS)
        entries: List[Dict[str, Any]] = []
        buffer: List[str] = []

        def _flush(buf: List[str]) -> None:
            if not buf:
                return
            combined = " | ".join(buf)
            entry: Dict[str, Any] = {
                "institution": None,
                "degree": None,
                "field_of_study": None,
                "year": None,
            }
            # Try to find a year
            year_match = re.search(r"\b(19|20)\d{2}\b", combined)
            if year_match:
                entry["year"] = year_match.group(0)

            # Simple heuristic: first line is often institution or degree
            if buf:
                entry["institution"] = buf[0].strip()
            if len(buf) > 1:
                degree_line = buf[1].strip()
                # Try to split "Degree in Field"
                in_match = re.match(
                    r"(.+?)\s+in\s+(.+)", degree_line, re.IGNORECASE
                )
                if in_match:
                    entry["degree"] = in_match.group(1).strip()
                    entry["field_of_study"] = in_match.group(2).strip()
                else:
                    entry["degree"] = degree_line
            entries.append(entry)

        for line in section:
            stripped = line.strip()
            if not stripped:
                _flush(buffer)
                buffer = []
                continue
            buffer.append(stripped)

        _flush(buffer)
        return entries

    @staticmethod
    def _extract_location(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Try to find a city / region / country in the full text."""
        m = _LOCATION_RE.search(text)
        if m:
            return (
                m.group("city").strip() if m.group("city") else None,
                m.group("region").strip() if m.group("region") else None,
                m.group("country").strip() if m.group("country") else None,
            )
        return None, None, None
