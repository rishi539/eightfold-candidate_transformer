"""
Country normaliser — converts country names / codes to ISO-3166 alpha-2.

Covers 30+ countries with common aliases, ISO alpha-3, and local names.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Complete set of valid ISO-3166 alpha-2 codes (subset of most common)
# used for the "already a 2-letter code?" fast-path.
# ------------------------------------------------------------------ #
_VALID_ISO2 = frozenset({
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AR", "AS", "AT",
    "AU", "AW", "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI",
    "BJ", "BM", "BN", "BO", "BR", "BS", "BT", "BW", "BY", "BZ", "CA",
    "CD", "CF", "CG", "CH", "CI", "CL", "CM", "CN", "CO", "CR", "CU",
    "CV", "CY", "CZ", "DE", "DJ", "DK", "DM", "DO", "DZ", "EC", "EE",
    "EG", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR", "GA",
    "GB", "GD", "GE", "GH", "GI", "GL", "GM", "GN", "GQ", "GR", "GT",
    "GU", "GW", "GY", "HK", "HN", "HR", "HT", "HU", "ID", "IE", "IL",
    "IN", "IQ", "IR", "IS", "IT", "JM", "JO", "JP", "KE", "KG", "KH",
    "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC",
    "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD",
    "ME", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MR", "MS",
    "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF",
    "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE",
    "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW",
    "PY", "QA", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE",
    "SG", "SH", "SI", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST",
    "SV", "SY", "SZ", "TC", "TD", "TG", "TH", "TJ", "TK", "TL", "TM",
    "TN", "TO", "TR", "TT", "TV", "TW", "TZ", "UA", "UG", "US", "UY",
    "UZ", "VA", "VC", "VE", "VG", "VI", "VN", "VU", "WF", "WS", "YE",
    "YT", "ZA", "ZM", "ZW",
})

# ------------------------------------------------------------------ #
# Alias map:  lowercase alias → ISO-3166 alpha-2 code
# ------------------------------------------------------------------ #
COUNTRY_ALIASES = {
    # India
    "india": "IN",
    "ind": "IN",
    "bharat": "IN",
    "hindustan": "IN",
    "republic of india": "IN",

    # United States
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "america": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "the united states": "US",

    # United Kingdom
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "gb": "GB",
    "england": "GB",
    "britain": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "u.k.": "GB",

    # Canada
    "canada": "CA",
    "ca": "CA",
    "can": "CA",

    # Australia
    "australia": "AU",
    "au": "AU",
    "aus": "AU",
    "oz": "AU",

    # Germany
    "germany": "DE",
    "de": "DE",
    "deu": "DE",
    "deutschland": "DE",
    "federal republic of germany": "DE",

    # France
    "france": "FR",
    "fr": "FR",
    "fra": "FR",
    "république française": "FR",

    # Japan
    "japan": "JP",
    "jp": "JP",
    "jpn": "JP",
    "nippon": "JP",

    # China
    "china": "CN",
    "cn": "CN",
    "chn": "CN",
    "people's republic of china": "CN",
    "prc": "CN",

    # Brazil
    "brazil": "BR",
    "br": "BR",
    "bra": "BR",
    "brasil": "BR",

    # Singapore
    "singapore": "SG",
    "sg": "SG",
    "sgp": "SG",

    # South Korea
    "south korea": "KR",
    "korea": "KR",
    "kr": "KR",
    "kor": "KR",
    "republic of korea": "KR",

    # Netherlands
    "netherlands": "NL",
    "nl": "NL",
    "nld": "NL",
    "holland": "NL",
    "the netherlands": "NL",

    # Italy
    "italy": "IT",
    "it": "IT",
    "ita": "IT",
    "italia": "IT",

    # Spain
    "spain": "ES",
    "es": "ES",
    "esp": "ES",
    "españa": "ES",

    # Sweden
    "sweden": "SE",
    "se": "SE",
    "swe": "SE",
    "sverige": "SE",

    # Switzerland
    "switzerland": "CH",
    "ch": "CH",
    "che": "CH",
    "swiss": "CH",

    # Ireland
    "ireland": "IE",
    "ie": "IE",
    "irl": "IE",
    "éire": "IE",

    # Israel
    "israel": "IL",
    "il": "IL",
    "isr": "IL",

    # New Zealand
    "new zealand": "NZ",
    "nz": "NZ",
    "nzl": "NZ",
    "aotearoa": "NZ",

    # Mexico
    "mexico": "MX",
    "mx": "MX",
    "mex": "MX",
    "méxico": "MX",

    # Russia
    "russia": "RU",
    "ru": "RU",
    "rus": "RU",
    "russian federation": "RU",

    # South Africa
    "south africa": "ZA",
    "za": "ZA",
    "zaf": "ZA",

    # United Arab Emirates
    "united arab emirates": "AE",
    "uae": "AE",
    "ae": "AE",
    "are": "AE",

    # Indonesia
    "indonesia": "ID",
    "id": "ID",
    "idn": "ID",

    # Malaysia
    "malaysia": "MY",
    "my": "MY",
    "mys": "MY",

    # Thailand
    "thailand": "TH",
    "th": "TH",
    "tha": "TH",

    # Philippines
    "philippines": "PH",
    "ph": "PH",
    "phl": "PH",
    "the philippines": "PH",

    # Pakistan
    "pakistan": "PK",
    "pk": "PK",
    "pak": "PK",

    # Bangladesh
    "bangladesh": "BD",
    "bd": "BD",
    "bgd": "BD",

    # Nigeria
    "nigeria": "NG",
    "ng": "NG",
    "nga": "NG",

    # Egypt
    "egypt": "EG",
    "eg": "EG",
    "egy": "EG",

    # Poland
    "poland": "PL",
    "pl": "PL",
    "pol": "PL",
    "polska": "PL",

    # Argentina
    "argentina": "AR",
    "ar": "AR",
    "arg": "AR",

    # Colombia
    "colombia": "CO",
    "co": "CO",
    "col": "CO",

    # Chile
    "chile": "CL",
    "cl": "CL",
    "chl": "CL",

    # Portugal
    "portugal": "PT",
    "pt": "PT",
    "prt": "PT",

    # Austria
    "austria": "AT",
    "at": "AT",
    "aut": "AT",
    "österreich": "AT",

    # Denmark
    "denmark": "DK",
    "dk": "DK",
    "dnk": "DK",
    "danmark": "DK",

    # Norway
    "norway": "NO",
    "no": "NO",
    "nor": "NO",
    "norge": "NO",

    # Finland
    "finland": "FI",
    "fi": "FI",
    "fin": "FI",
    "suomi": "FI",

    # Belgium
    "belgium": "BE",
    "be": "BE",
    "bel": "BE",

    # Czech Republic
    "czech republic": "CZ",
    "czechia": "CZ",
    "cz": "CZ",
    "cze": "CZ",

    # Romania
    "romania": "RO",
    "ro": "RO",
    "rou": "RO",

    # Vietnam
    "vietnam": "VN",
    "vn": "VN",
    "vnm": "VN",
    "viet nam": "VN",

    # Taiwan
    "taiwan": "TW",
    "tw": "TW",
    "twn": "TW",

    # Hong Kong
    "hong kong": "HK",
    "hk": "HK",
    "hkg": "HK",

    # Sri Lanka
    "sri lanka": "LK",
    "lk": "LK",
    "lka": "LK",

    # Kenya
    "kenya": "KE",
    "ke": "KE",
    "ken": "KE",

    # Turkey
    "turkey": "TR",
    "tr": "TR",
    "tur": "TR",
    "türkiye": "TR",

    # Ukraine
    "ukraine": "UA",
    "ua": "UA",
    "ukr": "UA",

    # Greece
    "greece": "GR",
    "gr": "GR",
    "grc": "GR",
    "hellas": "GR",

    # Hungary
    "hungary": "HU",
    "hu": "HU",
    "hun": "HU",
}


def normalize_country(raw: str) -> Optional[str]:
    """Normalise a raw country string to an ISO-3166 alpha-2 code.

    Parameters
    ----------
    raw:
        Country name, abbreviation, ISO alpha-2, or ISO alpha-3 code.

    Returns
    -------
    str | None
        Two-letter ISO code in upper case, or ``None`` if the input
        is unrecognised.
    """
    if not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    try:
        # Fast-path: already a valid 2-letter ISO code
        upper = cleaned.upper()
        if len(upper) == 2 and upper in _VALID_ISO2:
            return upper

        # Lookup in alias map (lowercase)
        lookup = cleaned.lower()
        code = COUNTRY_ALIASES.get(lookup)
        if code:
            return code

        # Try stripping common leading articles
        for prefix in ("the ", "republic of "):
            if lookup.startswith(prefix):
                code = COUNTRY_ALIASES.get(lookup[len(prefix):])
                if code:
                    return code

        return None

    except Exception:  # noqa: BLE001
        logger.debug("Country normalisation failed for %r", raw, exc_info=True)
        return None
