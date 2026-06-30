"""
Schema Validator
================
Validates candidate profile dictionaries against the canonical schema.

Tries to use the ``jsonschema`` library for thorough structural validation.
If unavailable, falls back to a lightweight manual validator that covers
required fields, type checks, and format checks.

Additional semantic checks (phone E.164, date YYYY-MM, country ISO-3166
alpha-2) are always applied regardless of the validation backend.
"""

import re
from typing import Tuple, List, Dict, Any, Optional, Union

# ---------------------------------------------------------------------------
# Canonical schema definition
# ---------------------------------------------------------------------------

CANONICAL_SCHEMA: Dict[str, Any] = {
    'type': 'object',
    'required': ['candidate_id', 'full_name', 'emails', 'phones', 'overall_confidence'],
    'properties': {
        'candidate_id': {'type': 'string'},
        'full_name': {'type': ['string', 'null']},
        'emails': {'type': 'array', 'items': {'type': 'string'}},
        'phones': {'type': 'array', 'items': {'type': 'string'}},
        'location': {
            'type': ['object', 'null'],
            'properties': {
                'city': {'type': ['string', 'null']},
                'region': {'type': ['string', 'null']},
                'country': {'type': ['string', 'null']},
            },
        },
        'links': {
            'type': ['object', 'null'],
            'properties': {
                'linkedin': {'type': ['string', 'null']},
                'github': {'type': ['string', 'null']},
                'portfolio': {'type': ['string', 'null']},
                'other': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
        'headline': {'type': ['string', 'null']},
        'total_years_experience': {'type': ['number', 'null']},
        'skills': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'confidence': {'type': 'number'},
                    'sources': {'type': 'array', 'items': {'type': 'string'}},
                },
            },
        },
        'experience': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'company': {'type': ['string', 'null']},
                    'title': {'type': ['string', 'null']},
                    'start': {'type': ['string', 'null']},
                    'end': {'type': ['string', 'null']},
                    'summary': {'type': ['string', 'null']},
                },
            },
        },
        'education': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'institution': {'type': ['string', 'null']},
                    'degree': {'type': ['string', 'null']},
                    'field': {'type': ['string', 'null']},
                    'end_year': {'type': ['integer', 'null']},
                },
            },
        },
        'provenance': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'field': {'type': 'string'},
                    'source': {'type': 'string'},
                    'method': {'type': 'string'},
                },
            },
        },
        'overall_confidence': {'type': 'number', 'minimum': 0, 'maximum': 1},
    },
}

# ---------------------------------------------------------------------------
# Regex patterns for semantic format checks
# ---------------------------------------------------------------------------

# E.164: starts with '+', followed by 1–15 digits
_E164_RE = re.compile(r'^\+\d{1,15}$')

# YYYY-MM date format
_YYYY_MM_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')

# ISO-3166 alpha-2 country code (exactly two uppercase ASCII letters)
_COUNTRY_RE = re.compile(r'^[A-Z]{2}$')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_output(output: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a candidate profile dict against the canonical schema.

    Returns
    -------
    Tuple[bool, List[str]]
        A two-tuple of (is_valid, errors) where *errors* is a list of
        human-readable error strings.  ``is_valid`` is ``True`` only when
        ``errors`` is empty.
    """
    try:
        errors: List[str] = []

        # --- structural / type validation ---
        errors.extend(_structural_validation(output))

        # --- semantic format checks ---
        errors.extend(_semantic_checks(output))

        return (len(errors) == 0, errors)
    except Exception as exc:
        return False, [f'Unexpected validation error: {exc}']


# ---------------------------------------------------------------------------
# Structural validation (jsonschema or manual fallback)
# ---------------------------------------------------------------------------

def _structural_validation(output: Dict[str, Any]) -> List[str]:
    """Run structural / type checks against the canonical schema."""
    try:
        import jsonschema  # type: ignore[import-untyped]
        return _validate_with_jsonschema(output)
    except ImportError:
        return _validate_manually(output)


def _validate_with_jsonschema(output: Dict[str, Any]) -> List[str]:
    """Validate using the ``jsonschema`` library."""
    import jsonschema  # type: ignore[import-untyped]

    errors: List[str] = []
    validator = jsonschema.Draft7Validator(CANONICAL_SCHEMA)
    for error in sorted(validator.iter_errors(output), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in error.absolute_path) or '(root)'
        errors.append(f'Schema error at {path}: {error.message}')
    return errors


# ---------------------------------------------------------------------------
# Manual fallback validator
# ---------------------------------------------------------------------------

# Maps JSON-schema type names to Python types.
_TYPE_MAP: Dict[str, type] = {
    'string': str,
    'number': (int, float),  # type: ignore[assignment]
    'integer': int,
    'boolean': bool,
    'array': list,
    'object': dict,
}


def _python_types_for(type_spec: Union[str, List[str]]) -> tuple:
    """Convert a JSON-schema *type* value to a tuple of Python types.

    ``'null'`` is mapped to ``type(None)``.
    """
    if isinstance(type_spec, str):
        type_spec = [type_spec]

    py_types: list = []
    for t in type_spec:
        if t == 'null':
            py_types.append(type(None))
        else:
            mapped = _TYPE_MAP.get(t)
            if mapped is not None:
                if isinstance(mapped, tuple):
                    py_types.extend(mapped)
                else:
                    py_types.append(mapped)
    return tuple(py_types)


def _validate_manually(output: Dict[str, Any]) -> List[str]:
    """Lightweight manual validation when *jsonschema* is not installed."""
    errors: List[str] = []

    if not isinstance(output, dict):
        return [f'Output must be a dict, got {type(output).__name__}']

    # --- required fields ---
    for field in CANONICAL_SCHEMA.get('required', []):
        if field not in output:
            errors.append(f'Missing required field: {field}')

    properties = CANONICAL_SCHEMA.get('properties', {})

    for field, spec in properties.items():
        if field not in output:
            continue

        value = output[field]

        # Type check
        expected_types = _python_types_for(spec.get('type', 'string'))
        if not isinstance(value, expected_types):
            errors.append(
                f'Field "{field}" has type {type(value).__name__}, '
                f'expected one of {spec.get("type")}'
            )
            continue  # skip deeper checks if type is wrong

        # Numeric range
        if isinstance(value, (int, float)) and value is not True and value is not False:
            if 'minimum' in spec and value < spec['minimum']:
                errors.append(
                    f'Field "{field}" value {value} is below minimum {spec["minimum"]}'
                )
            if 'maximum' in spec and value > spec['maximum']:
                errors.append(
                    f'Field "{field}" value {value} is above maximum {spec["maximum"]}'
                )

        # Array item checks
        if isinstance(value, list) and 'items' in spec:
            item_spec = spec['items']
            item_types = _python_types_for(item_spec.get('type', 'string'))
            for idx, item in enumerate(value):
                if not isinstance(item, item_types):
                    errors.append(
                        f'Field "{field}[{idx}]" has type '
                        f'{type(item).__name__}, expected {item_spec.get("type")}'
                    )
                # Nested object property checks
                if isinstance(item, dict) and 'properties' in item_spec:
                    for prop, prop_spec in item_spec['properties'].items():
                        if prop in item:
                            prop_types = _python_types_for(
                                prop_spec.get('type', 'string')
                            )
                            if not isinstance(item[prop], prop_types):
                                errors.append(
                                    f'Field "{field}[{idx}].{prop}" has type '
                                    f'{type(item[prop]).__name__}, '
                                    f'expected {prop_spec.get("type")}'
                                )

        # Nested object property checks (non-array)
        if isinstance(value, dict) and 'properties' in spec:
            for prop, prop_spec in spec['properties'].items():
                if prop in value:
                    prop_types = _python_types_for(
                        prop_spec.get('type', 'string')
                    )
                    if not isinstance(value[prop], prop_types):
                        errors.append(
                            f'Field "{field}.{prop}" has type '
                            f'{type(value[prop]).__name__}, '
                            f'expected {prop_spec.get("type")}'
                        )

    return errors


# ---------------------------------------------------------------------------
# Semantic / format checks
# ---------------------------------------------------------------------------

def _semantic_checks(output: Dict[str, Any]) -> List[str]:
    """Run format checks that go beyond JSON-schema structural validation."""
    errors: List[str] = []

    # --- Phone numbers: E.164 ---
    for idx, phone in enumerate(output.get('phones', []) or []):
        if isinstance(phone, str) and phone:
            if not _E164_RE.match(phone):
                errors.append(
                    f'phones[{idx}] "{phone}" does not match E.164 format '
                    f'(expected: +<digits>)'
                )

    # --- Date fields in experience: YYYY-MM ---
    for idx, exp in enumerate(output.get('experience', []) or []):
        if not isinstance(exp, dict):
            continue
        for date_field in ('start', 'end'):
            date_val = exp.get(date_field)
            if isinstance(date_val, str) and date_val:
                if not _YYYY_MM_RE.match(date_val):
                    errors.append(
                        f'experience[{idx}].{date_field} "{date_val}" '
                        f'does not match YYYY-MM format'
                    )

    # --- Country code: ISO-3166 alpha-2 ---
    location = output.get('location')
    if isinstance(location, dict):
        country = location.get('country')
        if isinstance(country, str) and country:
            if not _COUNTRY_RE.match(country):
                errors.append(
                    f'location.country "{country}" does not match '
                    f'ISO-3166 alpha-2 format (expected: two uppercase letters)'
                )

    return errors
