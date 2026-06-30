"""
DOCX parser stub for resume / CV documents in Microsoft Word format.

Uses **python-docx** to extract text and applies the same extraction
logic as the PDF parser (albeit with cleaner input text).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from models.candidate import RawExtraction
from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

# Reuse regex patterns identical to those in pdf_parser
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

_PHONE_RE = re.compile(
    r"""
    (?:
        (?:\+?\d{1,3}[\s\-.]?)?
        (?:\(?\d{2,4}\)?[\s\-.]?)?
        \d{3,4}[\s\-.]?\d{3,4}
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


class DOCXParser(BaseParser):
    """Extract candidate data from a DOCX resume / CV.

    This is a minimal stub that extracts full text and pulls out basic
    contact fields via regex.  It mirrors :class:`PDFParser` but benefits
    from the cleaner paragraph-based text that *python-docx* provides.
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def can_handle(self, source_path: str) -> bool:
        """Return ``True`` for ``.docx`` files."""
        return os.path.splitext(source_path)[1].lower() == ".docx"

    def parse(self, source_path: str) -> list[RawExtraction]:
        """Parse a DOCX resume and return a single-element list."""
        text = self._extract_text(source_path)
        if text is None:
            return [
                RawExtraction(
                    source_name="resume_docx",
                    source_file=source_path,
                    is_valid=False,
                    warnings=["Failed to extract text from DOCX."],
                )
            ]

        warnings: List[str] = []
        if not text.strip():
            warnings.append("DOCX file contains no extractable text.")
            return [
                RawExtraction(
                    source_name="resume_docx",
                    source_file=source_path,
                    data={},
                    warnings=warnings,
                    is_valid=False,
                )
            ]

        lines = text.splitlines()

        # --- Contact info ---------------------------------------------------
        emails = list(dict.fromkeys(_EMAIL_RE.findall(text)))
        phones = self._extract_phones(text)
        linkedin = self._first_match(_LINKEDIN_RE, text)
        github = self._first_match(_GITHUB_RE, text)

        # --- Name (heuristic: first non-empty, non-contact line) -----------
        name = self._extract_name(lines, set(emails))

        data: Dict[str, Any] = {
            "full_name": name,
            "emails": emails,
            "phones": phones,
            "linkedin": linkedin,
            "github": github,
        }

        return [
            RawExtraction(
                source_name="resume_docx",
                source_file=source_path,
                data=data,
                warnings=warnings,
                is_valid=True,
            )
        ]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text(path: str) -> Optional[str]:
        """Use *python-docx* to extract paragraph text."""
        try:
            import docx  # type: ignore[import-untyped]
        except ImportError:
            logger.error(
                "python-docx is not installed. "
                "Install it with: pip install python-docx"
            )
            return None

        try:
            doc = docx.Document(path)
            paragraphs = [p.text for p in doc.paragraphs]
            return "\n".join(paragraphs)
        except Exception as exc:
            logger.warning("Could not read DOCX %s: %s", path, exc)
            return None

    @staticmethod
    def _first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _extract_phones(text: str) -> List[str]:
        raw = _PHONE_RE.findall(text)
        phones: List[str] = []
        for phone in raw:
            digits = re.sub(r"\D", "", phone)
            if 7 <= len(digits) <= 15:
                phones.append(phone.strip())
        return list(dict.fromkeys(phones))

    @staticmethod
    def _extract_name(lines: List[str], email_set: set) -> Optional[str]:
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped in email_set or _EMAIL_RE.fullmatch(stripped):
                continue
            if stripped.startswith("http") or "@" in stripped:
                continue
            if len(stripped) > 60:
                continue
            letter_ratio = sum(
                c.isalpha() or c.isspace() for c in stripped
            ) / max(len(stripped), 1)
            if letter_ratio > 0.7:
                return stripped
        return None
