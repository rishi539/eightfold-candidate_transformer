import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projection.projector import project, resolve_path


class TestResolvePath:
    def setup_method(self):
        self.data = {
            'full_name': 'Alice Johnson',
            'emails': ['alice@test.com', 'alice2@test.com'],
            'phones': ['+15550101'],
            'location': {
                'city': 'San Francisco',
                'region': 'CA',
                'country': 'US'
            },
            'skills': [
                {'name': 'Python', 'confidence': 0.9},
                {'name': 'React', 'confidence': 0.8}
            ],
            'links': {
                'github': 'https://github.com/alice',
                'linkedin': None
            }
        }
    
    def test_simple_path(self):
        assert resolve_path(self.data, 'full_name') == 'Alice Johnson'
    
    def test_indexed_path(self):
        assert resolve_path(self.data, 'emails[0]') == 'alice@test.com'
    
    def test_nested_path(self):
        assert resolve_path(self.data, 'location.country') == 'US'
    
    def test_array_projection(self):
        result = resolve_path(self.data, 'skills[].name')
        assert result == ['Python', 'React']
    
    def test_missing_path(self):
        result = resolve_path(self.data, 'nonexistent')
        assert result is None
    
    def test_out_of_bounds(self):
        result = resolve_path(self.data, 'emails[99]')
        assert result is None


class TestProjection:
    def test_select_fields(self):
        canonical = {
            'candidate_id': '123',
            'full_name': 'Alice',
            'emails': ['alice@test.com'],
            'phones': ['+15550101'],
            'skills': [{'name': 'Python'}],
            'overall_confidence': 0.85,
            'provenance': []
        }
        config = {
            'fields': [
                {'path': 'full_name', 'type': 'string', 'required': True},
                {'from': 'emails[0]', 'path': 'primary_email', 'type': 'string'}
            ],
            'include_confidence': True,
            'include_provenance': False,
            'missing_value': 'null'
        }
        result = project(canonical, config)
        assert 'full_name' in result
        assert 'primary_email' in result
        assert result['primary_email'] == 'alice@test.com'
        assert 'overall_confidence' in result
        assert 'provenance' not in result
