# scripts/metrics/calculate_quality_metrics.py
"""
Calculate data quality metrics from validation results.
"""
import argparse
from pathlib import Path
import json
from typing import Dict, List
from collections import defaultdict


def calculate_metrics(results_dir: Path) -> Dict:
    """
    Calculate comprehensive quality metrics.
    
    Args:
        results_dir: Directory containing validation results
        
    Returns:
        Dict of calculated metrics
    """
    # Load all reports
    report_files = list(results_dir.glob('*_report.json'))
    reports = []
    for report_file in report_files:
        with open(report_file, 'r') as f:
            reports.append(json.load(f))
    
    if not reports:
        return {}
    
    # Calculate metrics
    metrics = {
        'total_datasets': len(reports),
        'decisions': defaultdict(int),
        'stages': defaultdict(lambda: defaultdict(int)),
        'issue_counts': defaultdict(int),
        'execution_times': [],
        'records_processed': 0
    }
    
    for report in reports:
        # Decision counts
        decision = report.get('final_decision', 'UNKNOWN')
        metrics['decisions'][decision] += 1
        
        # Execution times
        exec_time = report.get('execution_time_seconds', 0)
        metrics['execution_times'].append(exec_time)
        
        # Stage analysis
        for stage_name, stage_data in report.get('stages', {}).items():
            metrics['stages'][stage_name]['executed'] += 1
            if stage_data.get('passed'):
                metrics['stages'][stage_name]['passed'] += 1
            
            # Issue counts by severity
            for issue in stage_data.get('issues', []):
                severity = issue.get('severity', 'unknown')
                metrics['issue_counts'][severity] += 1
            
            # Records processed
            records = stage_data.get('records_processed', 0)
            metrics['records_processed'] += records
    
    # Calculate aggregates
    metrics['avg_execution_time'] = (
        sum(metrics['execution_times']) / len(metrics['execution_times'])
        if metrics['execution_times'] else 0
    )
    metrics['max_execution_time'] = max(metrics['execution_times']) if metrics['execution_times'] else 0
    metrics['min_execution_time'] = min(metrics['execution_times']) if metrics['execution_times'] else 0
    
    # Success rate
    total = metrics['total_datasets']
    accepted = metrics['decisions']['ACCEPTED'] + metrics['decisions']['CONDITIONAL_ACCEPT']
    metrics['success_rate'] = (accepted / total * 100) if total > 0 else 0
    
    # Convert defaultdicts to regular dicts for JSON serialization
    metrics['decisions'] = dict(metrics['decisions'])
    metrics['stages'] = {k: dict(v) for k, v in metrics['stages'].items()}
    metrics['issue_counts'] = dict(metrics['issue_counts'])
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description='Calculate quality metrics')
    parser.add_argument('--results-dir', type=str, required=True,
                        help='Directory containing validation results')
    parser.add_argument('--output', type=str, default='metrics.json',
                        help='Output metrics file')
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    metrics = calculate_metrics(results_dir)
    
    # Save metrics
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"Metrics calculated and saved to: {output_path}")
    print("\nSummary:")
    print(f"  Total datasets: {metrics['total_datasets']}")
    print(f"  Success rate: {metrics['success_rate']:.1f}%")
    print(f"  Avg execution time: {metrics['avg_execution_time']:.2f}s")
    print(f"  Total issues: {sum(metrics['issue_counts'].values())}")


if __name__ == "__main__":
    main()