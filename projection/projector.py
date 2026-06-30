"""Projector - reshape canonical profile using runtime config.

Config specifies output fields, optional renaming (from/path), and missing-value policies.
Path syntax: `full_name`, `location.country`, `emails[0]`, `skills[].name` (fan-out).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Regex for indexed access (emails[0]) and fan-out (skills[])
_INDEXED_RE = re.compile(r'^([A-Za-z_]\w*)\[(\d+)]$')
_FANOUT_RE = re.compile(r'^([A-Za-z_]\w*)\[]$')

# Valid missing-value policies
_MISSING_POLICIES = {'null', 'omit', 'error'}


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and validate projection config from JSON file."""
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f'Config not found: {config_path}')

    with open(config_path, 'r', encoding='utf-8') as fh:
        config: Dict[str, Any] = json.load(fh)

    _validate_config(config)
    return config


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate config structure."""
    if not isinstance(config, dict):
        raise ValueError('Config must be an object')

    fields = config.get('fields')
    if fields is not None:
        if not isinstance(fields, list):
            raise ValueError('"fields" must be an array')
        for idx, field in enumerate(fields):
            if not isinstance(field, dict):
                raise ValueError(f'fields[{idx}] must be an object')
            if 'path' not in field and 'from' not in field:
                raise ValueError(f'fields[{idx}] needs "path" or "from"')

    missing_value = config.get('missing_value', 'null')
    if missing_value not in _MISSING_POLICIES:
        raise ValueError(f'"missing_value" must be {_MISSING_POLICIES}')


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve a dotted path (with optional array indexing) against *data*.

    Supported syntax:

    * ``full_name``            → ``data['full_name']``
    * ``emails[0]``            → ``data['emails'][0]``
    * ``skills[].name``        → ``[s['name'] for s in data['skills']]``
    * ``location.country``     → ``data['location']['country']``
    * ``links.github``         → ``data['links']['github']``

    Parameters
    ----------
    data : Dict[str, Any]
        The canonical profile dictionary to read from.
    path : str
        The dotted path expression.

    Returns
    -------
    Any
        The resolved value, or a sentinel ``_MISSING`` if the path cannot be
        resolved.
    """
    segments = path.split('.')
    res = _resolve_segments(data, segments)
    return None if res is _MISSING else res


class _MissingSentinel:
    """Singleton sentinel indicating a path could not be resolved."""

    _instance: Optional['_MissingSentinel'] = None

    def __new__(cls) -> '_MissingSentinel':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return '<MISSING>'

    def __bool__(self) -> bool:
        return False


_MISSING = _MissingSentinel()


def _resolve_segments(data: Any, segments: List[str]) -> Any:
    """Recursively resolve a list of path segments."""
    if not segments:
        return data

    segment = segments[0]
    rest = segments[1:]

    # --- Fan-out: ``skills[]`` ---
    fanout_match = _FANOUT_RE.match(segment)
    if fanout_match:
        key = fanout_match.group(1)
        if not isinstance(data, dict) or key not in data:
            return _MISSING
        arr = data[key]
        if not isinstance(arr, list):
            return _MISSING
        if not rest:
            return arr  # ``skills[]`` with no further segments → full array
        results: List[Any] = []
        for item in arr:
            resolved = _resolve_segments(item, rest)
            if resolved is not _MISSING:
                results.append(resolved)
        return results if results else _MISSING

    # --- Indexed: ``emails[0]`` ---
    indexed_match = _INDEXED_RE.match(segment)
    if indexed_match:
        key = indexed_match.group(1)
        index = int(indexed_match.group(2))
        if not isinstance(data, dict) or key not in data:
            return _MISSING
        arr = data[key]
        if not isinstance(arr, list):
            return _MISSING
        if index >= len(arr):
            return _MISSING
        return _resolve_segments(arr[index], rest)

    # --- Plain key ---
    if not isinstance(data, dict) or segment not in data:
        return _MISSING
    return _resolve_segments(data[segment], rest)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

def project(canonical: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Project a canonical candidate profile to a custom output shape.

    Parameters
    ----------
    canonical : Dict[str, Any]
        A full canonical profile dictionary.
    config : Dict[str, Any]
        A projection configuration dictionary (see module docstring for
        the expected format).

    Returns
    -------
    Dict[str, Any]
        The projected output dictionary.

    Raises
    ------
    ValueError
        If a required field is missing and ``missing_value`` is ``'error'``.
    """
    missing_policy: str = config.get('missing_value', 'null')
    include_confidence: bool = config.get('include_confidence', False)
    include_provenance: bool = config.get('include_provenance', False)

    result: Dict[str, Any] = {}

    # --- Process each field directive ---
    for field_spec in config.get('fields', []):
        # Determine source path and output key.
        source_path: str = field_spec.get('from') or field_spec.get('path', '')
        output_key: str = _derive_output_key(field_spec)

        # Resolve value from canonical data.
        value = resolve_path(canonical, source_path)

        # Apply runtime normalization
        norm = field_spec.get('normalize')
        if norm and value not in (_MISSING, None):
            if norm == 'E164':
                from normalizers.phone import normalize_phone
                if isinstance(value, list):
                    value = [normalize_phone(v) or v for v in value]
                else:
                    value = normalize_phone(value) or value
            elif norm == 'canonical':
                from normalizers.skill import normalize_skill
                if isinstance(value, list):
                    value = [normalize_skill(v) for v in value]
                else:
                    value = normalize_skill(value)

        if value is _MISSING or value is None:
            is_required = field_spec.get('required', False)

            if missing_policy == 'error' and is_required:
                raise ValueError(
                    f'Required field "{output_key}" (source path: '
                    f'"{source_path}") is missing from canonical profile'
                )
            elif missing_policy == 'omit':
                continue  # skip this field entirely
            else:
                # 'null' policy — include as None
                result[output_key] = None
        else:
            result[output_key] = value

    # --- Confidence ---
    if include_confidence and 'overall_confidence' not in result:
        conf = canonical.get('overall_confidence')
        if conf is not None:
            result['overall_confidence'] = conf

    # --- Provenance ---
    if include_provenance:
        prov = canonical.get('provenance')
        if prov is not None:
            result['provenance'] = prov
    else:
        # Explicitly remove provenance if it sneaked in via a field directive
        result.pop('provenance', None)

    return result


def _derive_output_key(field_spec: Dict[str, Any]) -> str:
    """Derive the output key name from a field specification.

    Rules:
    * If ``path`` is present, the output key is the last simple segment
      (e.g., ``location.country`` → ``country``, ``skills[].name`` → ``name``).
    * If only ``from`` is present, the same logic applies to ``from``.
    """
    path: str = field_spec.get('path') or field_spec.get('from', '')
    # Take the last segment and strip any array notation.
    last_segment = path.rsplit('.', maxsplit=1)[-1]
    # Remove index/fanout brackets: ``emails[0]`` → ``emails``
    clean = re.sub(r'\[\d*]', '', last_segment)
    return clean or path


# ---------------------------------------------------------------------------
# Projected output validation
# ---------------------------------------------------------------------------

def validate_projected_output(
    projected: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate a projected output against the field requirements in *config*.

    Checks that every field marked ``required: true`` in the config is
    present and non-null in *projected*.

    Parameters
    ----------
    projected : Dict[str, Any]
        The projected output dictionary.
    config : Dict[str, Any]
        The projection configuration.

    Returns
    -------
    Tuple[bool, List[str]]
        (is_valid, errors)
    """
    errors: List[str] = []

    for field_spec in config.get('fields', []):
        output_key = _derive_output_key(field_spec)
        is_required = field_spec.get('required', False)
        expected_type = field_spec.get('type')

        if is_required:
            if output_key not in projected:
                errors.append(f'Required field "{output_key}" is missing')
                continue
            if projected[output_key] is None:
                errors.append(f'Required field "{output_key}" is null')
                continue

        # Type check (best-effort, since projected values are dynamic)
        if output_key in projected and projected[output_key] is not None:
            _check_projected_type(output_key, projected[output_key], expected_type, errors)

    return (len(errors) == 0, errors)


def _check_projected_type(
    key: str,
    value: Any,
    expected_type: Optional[str],
    errors: List[str],
) -> None:
    """Append an error if *value* does not match the expected type."""
    if expected_type is None:
        return

    type_map: Dict[str, type] = {
        'string': str,
        'number': (int, float),  # type: ignore[dict-item]
        'integer': int,
        'boolean': bool,
        'array': list,
        'object': dict,
    }

    expected = type_map.get(expected_type)
    if expected is None:
        return  # unknown type — skip

    if not isinstance(value, expected):  # type: ignore[arg-type]
        errors.append(
            f'Field "{key}" has type {type(value).__name__}, '
            f'expected {expected_type}'
        )
