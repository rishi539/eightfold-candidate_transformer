import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.engine import TransformerPipeline


class TestPipeline:
    def get_input_dir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'input'
        )
    
    def get_config_dir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config'
        )
    
    def test_end_to_end_default(self):
        """Test full pipeline with default output."""
        pipeline = TransformerPipeline()
        sources = [
            os.path.join(self.get_input_dir(), 'candidates.csv'),
            os.path.join(self.get_input_dir(), 'ats_data.json'),
        ]
        sources = [s for s in sources if os.path.exists(s)]
        if not sources:
            pytest.skip('No sample input files found')
        
        results = pipeline.run(sources)
        
        assert isinstance(results, list)
        assert len(results) > 0
        
        for candidate in results:
            assert 'candidate_id' in candidate
            assert 'overall_confidence' in candidate
            assert 'provenance' in candidate
            assert isinstance(candidate['provenance'], list)
    
    def test_end_to_end_custom_config(self):
        """Test full pipeline with custom config."""
        pipeline = TransformerPipeline()
        sources = [
            os.path.join(self.get_input_dir(), 'candidates.csv'),
            os.path.join(self.get_input_dir(), 'ats_data.json'),
        ]
        sources = [s for s in sources if os.path.exists(s)]
        config_path = os.path.join(self.get_config_dir(), 'custom_config.json')
        
        if not sources or not os.path.exists(config_path):
            pytest.skip('Sample files not found')
        
        results = pipeline.run(sources, config_path)
        assert isinstance(results, list)
        assert len(results) > 0
    
    def test_missing_source(self):
        """Pipeline should handle missing sources gracefully."""
        pipeline = TransformerPipeline()
        results = pipeline.run(['nonexistent_file.csv'])
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_empty_sources(self):
        """Pipeline should handle empty source list."""
        pipeline = TransformerPipeline()
        results = pipeline.run([])
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_deterministic_output(self):
        """Same inputs should produce same output."""
        sources = [
            os.path.join(self.get_input_dir(), 'candidates.csv'),
        ]
        sources = [s for s in sources if os.path.exists(s)]
        if not sources:
            pytest.skip('No sample input files found')
        
        pipeline1 = TransformerPipeline()
        result1 = pipeline1.run(sources)
        
        pipeline2 = TransformerPipeline()
        result2 = pipeline2.run(sources)
        
        for r in result1:
            r.pop('candidate_id', None)
        for r in result2:
            r.pop('candidate_id', None)
            
        assert json.dumps(result1, sort_keys=True) == json.dumps(result2, sort_keys=True)
