import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from normalizers.phone import normalize_phone
from normalizers.date_normalizer import normalize_date, extract_year
from normalizers.skill import normalize_skill, deduplicate_skills
from normalizers.country import normalize_country


class TestPhoneNormalizer:
    def test_us_with_country_code(self):
        assert normalize_phone('+1-555-0101') == '+15550101'
    
    def test_us_without_country_code(self):
        result = normalize_phone('(555) 234-5678')
        assert result is not None
        assert result.startswith('+')
    
    def test_india_with_country_code(self):
        result = normalize_phone('+91-98765-43210')
        assert result == '+919876543210'
    
    def test_india_10_digit(self):
        result = normalize_phone('9876543210')
        assert result is not None
    
    def test_invalid_phone(self):
        assert normalize_phone('12345') is None
    
    def test_empty_string(self):
        assert normalize_phone('') is None
    
    def test_none_input(self):
        assert normalize_phone(None) is None
    
    def test_uk_phone(self):
        result = normalize_phone('+44-20-7946-0958')
        assert result is not None
        assert result.startswith('+44')


class TestDateNormalizer:
    def test_jan_2020(self):
        assert normalize_date('Jan 2020') == '2020-01'
    
    def test_slash_format(self):
        assert normalize_date('01/2020') == '2020-01'
    
    def test_iso_format(self):
        assert normalize_date('2020-01') == '2020-01'
    
    def test_full_month(self):
        assert normalize_date('January 2020') == '2020-01'
    
    def test_full_date(self):
        assert normalize_date('2020-01-15') == '2020-01'
    
    def test_invalid_date(self):
        assert normalize_date('32/13/2020') is None
    
    def test_empty_string(self):
        assert normalize_date('') is None
    
    def test_none_input(self):
        assert normalize_date(None) is None


class TestExtractYear:
    def test_integer(self):
        assert extract_year('2020') == 2020
    
    def test_from_date(self):
        assert extract_year('May 2022') == 2022
    
    def test_invalid(self):
        assert extract_year('invalid') is None


class TestSkillNormalizer:
    def test_javascript_variants(self):
        assert normalize_skill('js') == 'JavaScript'
        assert normalize_skill('javascript') == 'JavaScript'
        assert normalize_skill('Java Script') == 'JavaScript'
    
    def test_python_variants(self):
        assert normalize_skill('py') == 'Python'
        assert normalize_skill('python3') == 'Python'
    
    def test_react_variants(self):
        assert normalize_skill('reactjs') == 'React'
        assert normalize_skill('react.js') == 'React'
    
    def test_ml_abbreviation(self):
        assert normalize_skill('ML') == 'Machine Learning'
    
    def test_unknown_skill_preserved(self):
        result = normalize_skill('Super Coding++')
        assert result == 'Super Coding++'
    
    def test_deduplicate(self):
        skills = ['JavaScript', 'js', 'Python', 'py', 'React']
        result = deduplicate_skills(skills)
        assert 'JavaScript' in result
        assert 'Python' in result
        assert 'React' in result
        assert len(result) == 3


class TestCountryNormalizer:
    def test_full_name(self):
        assert normalize_country('India') == 'IN'
        assert normalize_country('United States') == 'US'
    
    def test_abbreviation(self):
        assert normalize_country('USA') == 'US'
        assert normalize_country('UK') == 'GB'
    
    def test_iso_code(self):
        assert normalize_country('US') == 'US'
        assert normalize_country('IN') == 'IN'
    
    def test_alternate_names(self):
        assert normalize_country('Bharat') == 'IN'
        assert normalize_country('America') == 'US'
        assert normalize_country('England') == 'GB'
    
    def test_unknown(self):
        assert normalize_country('Atlantis') is None
    
    def test_empty(self):
        assert normalize_country('') is None
