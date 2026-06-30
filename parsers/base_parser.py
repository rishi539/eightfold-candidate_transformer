"""
Abstract base class for all source parsers.

Every concrete parser (CSV, PDF, ATS JSON, …) must inherit from
:class:`BaseParser` and implement the two abstract methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.candidate import RawExtraction


class BaseParser(ABC):
    """Contract that every parser in the pipeline must satisfy."""

    @abstractmethod
    def parse(self, source_path: str) -> list[RawExtraction]:
        """Parse a source file and return one :class:`RawExtraction` per candidate.

        Args:
            source_path: Filesystem path to the source file.

        Returns:
            A list of :class:`RawExtraction` instances.  The list may be
            empty if the file contains no candidate data.
        """
        pass

    @abstractmethod
    def can_handle(self, source_path: str) -> bool:
        """Return ``True`` if this parser is able to process *source_path*.

        The check is typically extension-based but concrete parsers may
        add additional heuristics (e.g. sniffing a magic number).

        Args:
            source_path: Filesystem path to the source file.
        """
        pass
