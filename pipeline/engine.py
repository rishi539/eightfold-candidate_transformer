"""Pipeline Engine

Coordinates extraction → matching → merging → validation → projection workflow.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from models.candidate import CandidateProfile, RawExtraction
from parsers.csv_parser import CSVParser
from parsers.pdf_parser import PDFParser
from parsers.ats_parser import ATSParser
from validators.source_validator import validate_source
from validators.schema_validator import validate_output
from merge.matcher import match_candidates
from merge.merger import merge_extractions
from confidence.scorer import calculate_confidence
from projection.projector import load_config, project

logger = logging.getLogger(__name__)


class TransformerPipeline:
    """Main pipeline orchestrator for candidate data transformation."""

    def __init__(self) -> None:
        self.parsers = [CSVParser(), PDFParser(), ATSParser()]
        self.warnings: List[str] = []

    def run(
        self,
        source_paths: List[str],
        config_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run full transformation pipeline.
        
        Args:
            source_paths: File paths to ingest
            config_path: Optional projection config
            
        Returns:
            List of canonical (or projected) candidate profiles
        """
        self.warnings = []

        # Validate sources
        valid_sources: List[tuple[str, str]] = []
        seen_hashes = set()
        import hashlib
        for path in source_paths:
            is_valid, source_type, warnings = validate_source(path)
            self.warnings.extend(warnings)
            if is_valid:
                try:
                    with open(path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    if file_hash in seen_hashes:
                        logger.info('Skipping duplicate file: %s', path)
                        self.warnings.append(f'Skipped duplicate file: {path}')
                        continue
                    seen_hashes.add(file_hash)
                except Exception as e:
                    logger.error('Could not hash file %s: %s', path, e)
                    
                valid_sources.append((path, source_type))
            else:
                logger.warning('Skipping invalid source: %s', path)

        if not valid_sources:
            logger.error('No valid sources found')
            return []

        # Extract from all sources
        all_extractions: List[RawExtraction] = []
        for path, source_type in valid_sources:
            parser = self._get_parser(path)
            if parser is None:
                continue
            try:
                extractions = parser.parse(path)
                all_extractions.extend(extractions)
            except Exception as exc:
                logger.error('Error parsing %s: %s', path, exc)
                self.warnings.append(f'Failed to parse {path}: {exc}')

        if not all_extractions:
            logger.error('No data extracted')
            return []

        # Match candidates across sources
        candidate_groups = match_candidates(all_extractions)

        # Merge each group into a single profile
        profiles: List[CandidateProfile] = []
        for group in candidate_groups:
            try:
                profile = merge_extractions(group)
                profiles.append(profile)
            except Exception as exc:
                logger.error('Merge failed: %s', exc)
                self.warnings.append(f'Merge failed: {exc}')

        # Convert to dict and validate
        results: List[Dict[str, Any]] = []
        for profile in profiles:
            try:
                profile_dict = profile.to_dict()
            except Exception as exc:
                logger.error('Serialization failed for %s: %s', profile.candidate_id, exc)
                self.warnings.append(f'Serialization failed: {exc}')
                continue

            is_valid, errors = validate_output(profile_dict)
            if not is_valid:
                logger.warning('Validation errors: %s', errors)
                self.warnings.extend(errors)

            # Apply projection config if provided
            if config_path:
                try:
                    config = load_config(config_path)
                    profile_dict = project(profile_dict, config)
                except Exception as exc:
                    logger.error('Projection failed: %s', exc)
                    self.warnings.append(f'Projection failed: {exc}')
                    continue

            results.append(profile_dict)

        return results

    def _get_parser(self, file_path: str):
        """Return parser that can handle this file, or None."""
        for parser in self.parsers:
            if parser.can_handle(file_path):
                return parser
        logger.warning('No parser for: %s', file_path)
        self.warnings.append(f'No parser for: {file_path}')
        return None

    def get_warnings(self) -> List[str]:
        """Return warnings from last run."""
        return list(self.warnings)
