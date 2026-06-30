"""
Source Validator
================
Validates input source files before they enter the parsing pipeline.

Performs existence, size, extension, and format-specific structural checks.
Designed to NEVER crash — all exceptions are caught and returned as warnings.
"""

import os
import json
import csv
from typing import Tuple, List

# Supported file extensions mapped to their canonical source type names.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    '.csv': 'csv',
    '.json': 'json',
    '.pdf': 'pdf',
    '.docx': 'docx',
    '.txt': 'text',
}

# Upper bound for "reasonable" CSV column count — files with more columns
# than this trigger a warning (but are still considered valid).
_MAX_REASONABLE_CSV_COLUMNS = 100


def validate_source(file_path: str) -> Tuple[bool, str, List[str]]:
    """Validate a source file before processing.

    Runs a series of checks on the file at *file_path* and returns a
    three-tuple:

    * **is_valid** – ``True`` when the file can be forwarded to a parser.
    * **source_type** – one of ``'csv'``, ``'json'``, ``'pdf'``, ``'docx'``,
      ``'text'``, or ``'unknown'`` if the extension is not recognized.
    * **warnings** – a (possibly empty) list of human-readable warning /
      error strings describing any issues found.

    The function is intentionally defensive: it will **never** raise an
    exception.  Unexpected errors are caught and surfaced through the
    *warnings* list with ``is_valid`` set to ``False``.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the candidate source file.

    Returns
    -------
    Tuple[bool, str, List[str]]
    """
    try:
        return _validate_source_inner(file_path)
    except Exception as exc:  # pragma: no cover – ultimate safety net
        return False, 'unknown', [f'Unexpected validation error: {exc}']


# ------------------------------------------------------------------
# Internal implementation
# ------------------------------------------------------------------

def _validate_source_inner(file_path: str) -> Tuple[bool, str, List[str]]:
    """Core validation logic (may raise)."""
    warnings: List[str] = []

    # 1. Existence check
    if not os.path.exists(file_path):
        return False, 'unknown', [f'File does not exist: {file_path}']

    if not os.path.isfile(file_path):
        return False, 'unknown', [f'Path is not a regular file: {file_path}']

    # 2. Empty-file check
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, 'unknown', [f'File is empty: {file_path}']

    # 3. Extension check
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return False, 'unknown', [
            f'Unsupported file extension "{ext}". '
            f'Supported: {", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))}'
        ]

    source_type: str = SUPPORTED_EXTENSIONS[ext]

    # 4. Format-specific validation
    if source_type == 'json':
        _validate_json(file_path, warnings)
    elif source_type == 'csv':
        _validate_csv(file_path, warnings)
    elif source_type == 'pdf':
        _validate_pdf(file_path, warnings)
    # .docx and .txt have no additional structural checks — accept them
    # as-is after the basic checks above.

    # If any warning was generated the file *might* still be parseable, so
    # we only mark it invalid when one of the critical checks above already
    # returned early.  Format-specific helpers append warnings but do not
    # flip validity — the downstream parser decides whether to skip.
    is_valid = True

    # However, if a format check appended a *critical* warning (prefixed
    # with "CRITICAL:"), treat the source as invalid.
    for w in warnings:
        if w.startswith('CRITICAL:'):
            is_valid = False
            break

    return is_valid, source_type, warnings


def _validate_json(file_path: str, warnings: List[str]) -> None:
    """Attempt to parse the file as JSON; append warnings on failure."""
    try:
        with open(file_path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)

        # A JSON file that decodes to a scalar is unusual for candidate data.
        if not isinstance(data, (dict, list)):
            warnings.append(
                f'JSON root is {type(data).__name__}, expected object or array'
            )
        elif isinstance(data, list) and len(data) == 0:
            warnings.append('JSON file contains an empty array')
        elif isinstance(data, dict) and len(data) == 0:
            warnings.append('JSON file contains an empty object')
    except json.JSONDecodeError as exc:
        warnings.append(f'CRITICAL: Invalid JSON — {exc}')
    except UnicodeDecodeError as exc:
        warnings.append(f'CRITICAL: Cannot decode JSON file as UTF-8 — {exc}')


def _validate_csv(file_path: str, warnings: List[str]) -> None:
    """Read the first line of a CSV; check column count is reasonable."""
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as fh:
            reader = csv.reader(fh)
            try:
                header = next(reader)
            except StopIteration:
                warnings.append('CRITICAL: CSV file has no rows')
                return

            col_count = len(header)
            if col_count == 0:
                warnings.append('CRITICAL: CSV header row has no columns')
            elif col_count > _MAX_REASONABLE_CSV_COLUMNS:
                warnings.append(
                    f'CSV has {col_count} columns — unusually high; '
                    f'verify this is the correct file'
                )

            # Check if there is at least one data row beyond the header.
            try:
                first_row = next(reader)
                if len(first_row) != col_count:
                    warnings.append(
                        f'First data row has {len(first_row)} values but '
                        f'header has {col_count} columns'
                    )
            except StopIteration:
                warnings.append('CSV file contains only a header row — no data')
    except UnicodeDecodeError as exc:
        warnings.append(f'CRITICAL: Cannot decode CSV file as UTF-8 — {exc}')
    except csv.Error as exc:
        warnings.append(f'CRITICAL: CSV parsing error — {exc}')


def _validate_pdf(file_path: str, warnings: List[str]) -> None:
    """Try to open the PDF with *pdfplumber*; append warnings on failure."""
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        warnings.append(
            'pdfplumber is not installed — PDF validation skipped. '
            'Install with: pip install pdfplumber'
        )
        return

    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                warnings.append('PDF file has zero pages')
    except Exception as exc:
        warnings.append(f'CRITICAL: Failed to open PDF — {exc}')
