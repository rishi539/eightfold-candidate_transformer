"""
Canonical candidate profile data model.

Defines dataclasses for the unified candidate representation used across
all parsers and normalizers in the Multi-Source Candidate Data Transformer.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import uuid


@dataclass
class Skill:
    """A single skill with confidence score and source provenance."""
    name: str
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)


@dataclass
class Experience:
    """A single work-experience entry."""
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None   # YYYY-MM
    end: Optional[str] = None     # YYYY-MM
    summary: Optional[str] = None


@dataclass
class Education:
    """A single education entry."""
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None  # serialised as 'field' in output
    end_year: Optional[int] = None


@dataclass
class Location:
    """Geographic location with optional city / region / country."""
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


@dataclass
class Links:
    """Web presence links."""
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: List[str] = field(default_factory=list)


@dataclass
class Provenance:
    """Tracks the origin of a particular field value."""
    field_name: str   # serialised as 'field' in output
    source: str
    method: str


@dataclass
class CandidateProfile:
    """
    Canonical, merged candidate profile.

    All parsers normalise their output into this structure before the
    merger combines multiple profiles into one.
    """
    candidate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    full_name: Optional[str] = None
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    location: Optional[Location] = None
    links: Optional[Links] = None
    headline: Optional[str] = None
    total_years_experience: Optional[float] = None
    skills: List[Skill] = field(default_factory=list)
    experience: List[Experience] = field(default_factory=list)
    education: List[Education] = field(default_factory=list)
    provenance: List[Provenance] = field(default_factory=list)
    overall_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dictionary matching the output JSON schema."""
        result: Dict[str, Any] = {
            'candidate_id': self.candidate_id,
            'full_name': self.full_name,
            'emails': list(self.emails),
            'phones': list(self.phones),
            'location': (
                {
                    'city': self.location.city if self.location else None,
                    'region': self.location.region if self.location else None,
                    'country': self.location.country if self.location else None,
                }
                if self.location
                else None
            ),
            'links': (
                {
                    'linkedin': self.links.linkedin if self.links else None,
                    'github': self.links.github if self.links else None,
                    'portfolio': self.links.portfolio if self.links else None,
                    'other': list(self.links.other) if self.links else [],
                }
                if self.links
                else None
            ),
            'headline': self.headline,
            'total_years_experience': self.total_years_experience,
            'skills': [
                {
                    'name': s.name,
                    'confidence': s.confidence,
                    'sources': list(s.sources),
                }
                for s in self.skills
            ],
            'experience': [
                {
                    'company': e.company,
                    'title': e.title,
                    'start': e.start,
                    'end': e.end,
                    'summary': e.summary,
                }
                for e in self.experience
            ],
            'education': [
                {
                    'institution': ed.institution,
                    'degree': ed.degree,
                    'field': ed.field_of_study,
                    'end_year': ed.end_year,
                }
                for ed in self.education
            ],
            'provenance': [
                {
                    'field': p.field_name,
                    'source': p.source,
                    'method': p.method,
                }
                for p in self.provenance
            ],
            'overall_confidence': round(self.overall_confidence, 2),
        }
        return result


@dataclass
class RawExtraction:
    """Raw extracted data from a single source, before normalisation.

    Each parser produces one ``RawExtraction`` per input file / URL.
    The normaliser pipeline then converts the free-form ``data`` dict
    into a ``CandidateProfile``.
    """
    source_name: str          # e.g. 'csv', 'resume_pdf', 'ats_json', 'github'
    source_file: str          # file path or URL
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = True
