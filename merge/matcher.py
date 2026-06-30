"""Identity resolution using Union-Find.

Groups RawExtractions by shared identifiers: email, phone, LinkedIn, GitHub.
Excludes name-only matching to avoid false positives.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from models.candidate import RawExtraction
from normalizers.phone import normalize_phone

logger = logging.getLogger(__name__)


class _UnionFind:
    """Weighted quick-union with path compression."""

    def __init__(self, n: int) -> None:
        self._parent: List[int] = list(range(n))
        self._rank: List[int] = [0] * n

    def find(self, x: int) -> int:
        """Find root with path halving compression."""
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        """Merge sets by rank."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def _clean(value: Optional[str]) -> Optional[str]:
    """Strip and return None for empty strings."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _normalise_email(email: Optional[str]) -> Optional[str]:
    """Lowercase and strip email."""
    cleaned = _clean(email)
    return cleaned.lower() if cleaned else None


def _normalise_url(url: Optional[str]) -> Optional[str]:
    """Strip protocol, www, lowercase, and remove trailing slash."""
    cleaned = _clean(url)
    if cleaned is None:
        return None
    cleaned = cleaned.lower().rstrip("/")
    for prefix in ["https://www.", "http://www.", "https://", "http://", "www."]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned


def _normalise_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone number to E.164 or None."""
    cleaned = _clean(phone)
    if cleaned is None:
        return None
    try:
        normalised = normalize_phone(cleaned)
        return _clean(normalised)
    except Exception:
        logger.debug("Phone normalisation failed for value: %s", cleaned)
        return None


def match_candidates(extractions: List[RawExtraction]) -> List[List[RawExtraction]]:
    """Group extractions by shared identifiers (email, phone, LinkedIn, GitHub).
    
    Returns groups sorted by earliest extraction index for deterministic output.
    """
    if not extractions:
        return []

    n = len(extractions)
    uf = _UnionFind(n)

    # Identifier -> first extraction index lookup
    email_idx: Dict[str, int] = {}
    phone_idx: Dict[str, int] = {}
    linkedin_idx: Dict[str, int] = {}
    github_idx: Dict[str, int] = {}

    for i, ext in enumerate(extractions):
        # Match on email
        emails = ext.data.get("emails", [])
        if isinstance(emails, str):
            emails = [emails]
        for raw_email in emails:
            email = _normalise_email(raw_email)
            if email is None:
                continue
            if email in email_idx:
                uf.union(i, email_idx[email])
                logger.debug("Email match: %d ↔ %d", i, email_idx[email])
            else:
                email_idx[email] = i

        # Match on phone
        phones = ext.data.get("phones", [])
        if isinstance(phones, str):
            phones = [phones]
        for raw_phone in phones:
            phone = _normalise_phone(raw_phone)
            if phone is None:
                continue
            if phone in phone_idx:
                uf.union(i, phone_idx[phone])
                logger.debug("Phone match: %d ↔ %d", i, phone_idx[phone])
            else:
                phone_idx[phone] = i

        # --- LinkedIn ---
        linkedin_url = ext.data.get("linkedin")
        links = ext.data.get("links", {})
        if isinstance(links, dict) and "linkedin" in links:
            linkedin_url = links["linkedin"]
        elif getattr(links, "linkedin", None) is not None:
            linkedin_url = links.linkedin
        linkedin = _normalise_url(linkedin_url)
        if linkedin is not None:
            if linkedin in linkedin_idx:
                uf.union(i, linkedin_idx[linkedin])
                logger.debug(
                    "Matched extraction %d with %d on LinkedIn %s",
                    i, linkedin_idx[linkedin], linkedin,
                )
            else:
                linkedin_idx[linkedin] = i

        # --- GitHub ---
        github_url = ext.data.get("github")
        if isinstance(links, dict) and "github" in links:
            github_url = links["github"]
        elif getattr(links, "github", None) is not None:
            github_url = links.github
        github = _normalise_url(github_url)
        if github is not None:
            if github in github_idx:
                uf.union(i, github_idx[github])
                logger.debug(
                    "Matched extraction %d with %d on GitHub %s",
                    i, github_idx[github], github,
                )
            else:
                github_idx[github] = i

    # ---- Pass 2: Heuristic Name + Experience Matching ----
    # Merge candidates with identical names AND identical recent companies/titles
    for i in range(n):
        for j in range(i + 1, n):
            if uf.find(i) == uf.find(j):
                continue
            
            ext_i = extractions[i]
            ext_j = extractions[j]
            
            name_i = _clean(ext_i.data.get("full_name"))
            name_j = _clean(ext_j.data.get("full_name"))
            
            if not name_i or not name_j or name_i.lower() != name_j.lower():
                continue
                
            def get_comps_titles(cand: RawExtraction):
                comps, titles = set(), set()
                if c := _clean(cand.data.get("company")): comps.add(c.lower())
                if t := _clean(cand.data.get("title")): titles.add(t.lower())
                if h := _clean(cand.data.get("headline")): titles.add(h.lower())
                for e in cand.data.get("experience", []):
                    if c2 := _clean(e.get("company")): comps.add(c2.lower())
                    if t2 := _clean(e.get("title")): titles.add(t2.lower())
                return comps, titles

            c_i, t_i = get_comps_titles(ext_i)
            c_j, t_j = get_comps_titles(ext_j)
            
            overlap = bool(c_i & c_j) or bool(t_i & t_j)
                    
            if overlap:
                uf.union(i, j)
                logger.debug("Heuristic Name+Experience match: %d ↔ %d", i, j)

    # ---- Build groups ----
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups.setdefault(root, []).append(i)

    # Sort groups by their earliest member index (deterministic order)
    sorted_groups = sorted(groups.values(), key=lambda g: g[0])

    return [
        [extractions[i] for i in group]
        for group in sorted_groups
    ]
