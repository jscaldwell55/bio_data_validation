# scripts/validation/validate_datasets.py
"""
Batch validation script for datasets.
"""
import asyncio
import argparse
from pathlib import Path
import pandas as pd
import json
from datetime import datetime
import logging

from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import DatasetMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def validate_file(
    file_path: Path,
    orchestrator: ValidationOrchestrator,
    output_dir: Path
) -> dict:
    """
    Validate a single file.
    
    Args:
        file_path: Path to file to validate
        orchestrator: ValidationOrchestrator instance
        output_dir: Directory for output reports
        
    Returns:
        Validation report dict
    """
    logger.info(f"Validating: {file_path}")
    
    # Determine format from extension
    suffix = file_path.suffix.lower()
    format_map = {
        '.csv': 'guide_rna',
        '.fasta': 'fasta',
        '.fastq': 'fastq',
        '.json': 'json'
    }
    format_type = format_map.get(suffix, 'unknown')
    
    if format_type == 'unknown':
        logger.warning(f"Unknown format for {file_path}, skipping")
        return None
    
    # Load data
    if suffix == '.csv':
        df = pd.read_csv(file_path)
    elif suffix in ['.fasta', '.fastq']:
        with open(file_path, 'r') as f:
            df = f.read()
    elif suffix == '.json':
        with open(file_path, 'r') as f:
            df = json.load(f)
    else:
        logger.error(f"Cannot load {file_path}")
        return None
    
    # Create metadata
    metadata = DatasetMetadata(
        dataset_id=file_path.stem,
        format_type=format_type,
        record_count=len(df) if isinstance(df, pd.DataFrame) else 1,
        source=str(file_path)
    )
    
    # Validate
    try:
        report = await orchestrator.validate_dataset(df, metadata)
        
        # Save report
        report_path = output_dir / f"{file_path.stem}_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"✓ Validation complete: {report['final_decision']}")
        return report
        
    except Exception as e:
        logger.exception(f"✗ Validation failed: {str(e)}")
        return {
            'dataset_id': metadata.dataset_id,
            'error': str(e),
            'final_decision': 'ERROR'
        }


async def main():
    parser = argparse.ArgumentParser(description='Batch validate datasets')
    parser.add_argument('--input-dir', type=str, required=True,
                        help='Directory containing datasets to validate')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Directory for validation reports')
    parser.add_argument('--report-format', type=str, default='json',
                        help='Report format (json, html, both)')
    parser.add_argument('--parallel', type=int, default=4,
                        help='Number of parallel validations')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize orchestrator
    config = OrchestrationConfig(
        timeout_seconds=600,
        enable_short_circuit=True,
        enable_parallel_bio=True
    )
    orchestrator = ValidationOrchestrator(config)
    
    # Find all data files
    data_files = list(input_dir.glob('*.csv'))
    data_files.extend(input_dir.glob('*.fasta'))
    data_files.extend(input_dir.glob('*.fastq'))
    data_files.extend(input_dir.glob('*.json'))
    
    logger.info(f"Found {len(data_files)} files to validate")
    
    # Validate files
    reports = []
    for i in range(0, len(data_files), args.parallel):
        batch = data_files[i:i + args.parallel]
        tasks = [validate_file(f, orchestrator, output_dir) for f in batch]
        batch_reports = await asyncio.gather(*tasks)
        reports.extend([r for r in batch_reports if r is not None])
    
    # Generate summary
    summary = {
        'total_datasets': len(reports),
        'accepted': sum(1 for r in reports if r['final_decision'] == 'ACCEPTED'),
        'rejected': sum(1 for r in reports if r['final_decision'] == 'REJECTED'),
        'conditional': sum(1 for r in reports if r['final_decision'] == 'CONDITIONAL_ACCEPT'),
        'errors': sum(1 for r in reports if r['final_decision'] == 'ERROR'),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    summary_path = output_dir / 'validation_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"VALIDATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total datasets: {summary['total_datasets']}")
    logger.info(f"Accepted: {summary['accepted']}")
    logger.info(f"Rejected: {summary['rejected']}")
    logger.info(f"Conditional: {summary['conditional']}")
    logger.info(f"Errors: {summary['errors']}")
    logger.info(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())