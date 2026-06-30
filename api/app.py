"""REST API for the Candidate Data Transformer."""
import os
import sys
import json
import tempfile
import logging
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from pipeline.engine import TransformerPipeline

app = Flask(__name__)
CORS(app)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'json', 'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'version': '1.0.0'})

@app.route('/api/transform', methods=['POST'])
def transform():
    """Transform candidate data from uploaded sources.
    
    Expects multipart form data with:
    - files: one or more source files (JSON for structured, PDF/DOCX for resumes)
    - config: optional JSON config string or file
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400
    
    saved_paths: List[str] = []
    config_path = None
    
    try:
        # Save uploaded files
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                saved_paths.append(filepath)
            else:
                return jsonify({'error': f'Invalid file type: {file.filename}'}), 400
        
        # Handle config
        config_str = request.form.get('config')
        if config_str:
            try:
                config_data = json.loads(config_str)
                config_path = os.path.join(UPLOAD_FOLDER, '_runtime_config.json')
                with open(config_path, 'w') as f:
                    json.dump(config_data, f)
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid config JSON'}), 400
        
        if 'config_file' in request.files:
            config_file = request.files['config_file']
            if config_file and config_file.filename:
                config_path = os.path.join(UPLOAD_FOLDER, '_runtime_config.json')
                config_file.save(config_path)
        
        # Run pipeline
        pipeline = TransformerPipeline()
        results = pipeline.run(saved_paths, config_path)
        
        response = {
            'candidates': results,
            'metadata': {
                'source_count': len(saved_paths),
                'candidate_count': len(results),
                'warnings': pipeline.get_warnings()
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.exception('Transform failed')
        return jsonify({'error': str(e)}), 500
    
    finally:
        # Cleanup uploaded files
        for path in saved_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        if config_path and os.path.exists(config_path):
            try:
                os.remove(config_path)
            except OSError:
                pass

@app.route('/api/schema', methods=['GET'])
def get_schema():
    """Return the canonical output schema."""
    from validators.schema_validator import CANONICAL_SCHEMA
    return jsonify(CANONICAL_SCHEMA)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
