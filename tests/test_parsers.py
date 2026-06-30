import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.csv_parser import CSVParser
from parsers.ats_parser import ATSParser


class TestCSVParser:
    def test_can_handle_csv(self):
        parser = CSVParser()
        assert parser.can_handle('test.csv') is True
        assert parser.can_handle('test.json') is False
    
    def test_parse_sample_csv(self):
        parser = CSVParser()
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'input', 'candidates.csv'
        )
        if os.path.exists(csv_path):
            results = parser.parse(csv_path)
            assert len(results) > 0
            assert results[0].source_name == 'csv'
            assert results[0].is_valid is True
    
    def test_missing_file(self):
        parser = CSVParser()
        results = parser.parse('nonexistent.csv')
        assert len(results) == 0 or not results[0].is_valid


class TestATSParser:
    def test_can_handle_json(self):
        parser = ATSParser()
        assert parser.can_handle('test.json') is True
        assert parser.can_handle('test.csv') is False
    
    def test_parse_sample_json(self):
        parser = ATSParser()
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'input', 'ats_data.json'
        )
        if os.path.exists(json_path):
            results = parser.parse(json_path)
            assert len(results) > 0
            assert results[0].source_name == 'ats_json'
