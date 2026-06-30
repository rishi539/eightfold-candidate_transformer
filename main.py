#!/usr/bin/env python3
"""Multi-Source Candidate Data Transformer - CLI

Usage:
    python main.py --sources input/candidates.csv input/resume.pdf --output output/result.json
    python main.py --sources input/candidates.csv --config config/custom_config.json --output output/custom_result.json
"""
import argparse
import json
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.engine import TransformerPipeline

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(
        description='Multi-Source Candidate Data Transformer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --sources input/candidates.csv input/resume.pdf
  python main.py --sources input/candidates.csv --config config/custom_config.json
  python main.py --sources input/candidates.csv input/ats_data.json --output output/result.json
        """
    )
    parser.add_argument(
        '--sources', '-s',
        nargs='+',
        required=True,
        help='Input source file paths (CSV, JSON, PDF, DOCX, TXT)'
    )
    parser.add_argument(
        '--config', '-c',
        help='Path to projection config JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        default='output/result.json',
        help='Output JSON file path (default: output/result.json)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--pretty', '-p',
        action='store_true',
        default=True,
        help='Pretty-print JSON output (default: true)'
    )
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    # Run pipeline
    pipeline = TransformerPipeline()
    results = pipeline.run(args.sources, args.config)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    
    # Write output
    output_data = {
        'candidates': results,
        'metadata': {
            'source_count': len(args.sources),
            'candidate_count': len(results),
            'warnings': pipeline.get_warnings()
        }
    }
    
    indent = 2 if args.pretty else None
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=indent, ensure_ascii=False)
    
    # Also print to stdout
    print(json.dumps(output_data, indent=indent, ensure_ascii=False))
    
    print(f'\n✅ Output written to {args.output}', file=sys.stderr)
    print(f'📊 Processed {len(results)} candidate(s) from {len(args.sources)} source(s)', file=sys.stderr)
    
    if pipeline.get_warnings():
        print(f'⚠️  {len(pipeline.get_warnings())} warning(s) generated', file=sys.stderr)

if __name__ == '__main__':
    main()
