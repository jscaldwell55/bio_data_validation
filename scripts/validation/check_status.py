# scripts/validation/check_status.py
"""
Check validation status and optionally fail on errors.
"""
import argparse
import json
from pathlib import Path
import sys


def check_validation_status(results_dir: Path, fail_on_error: bool = False) -> int:
    """
    Check validation status from results.
    
    Args:
        results_dir: Directory containing validation results
        fail_on_error: Whether to exit with error code if validation failed
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    summary_path = results_dir / 'validation_summary.json'
    
    if not summary_path.exists():
        print("ERROR: No validation summary found")
        return 1
    
    with open(summary_path, 'r') as f:
        summary = json.load(f)
    
    print(f"\nValidation Status Check")
    print(f"{'='*60}")
    print(f"Total datasets: {summary['total_datasets']}")
    print(f"Accepted: {summary['accepted']}")
    print(f"Rejected: {summary['rejected']}")
    print(f"Errors: {summary['errors']}")
    
    # Determine if validation passed
    if summary['rejected'] > 0 or summary['errors'] > 0:
        print(f"\n❌ VALIDATION FAILED")
        print(f"   - {summary['rejected']} dataset(s) rejected")
        print(f"   - {summary['errors']} error(s) encountered")
        
        if fail_on_error:
            return 1
    else:
        print(f"\n✅ VALIDATION PASSED")
        print(f"   - All {summary['total_datasets']} dataset(s) validated successfully")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='Check validation status')
    parser.add_argument('--results-dir', type=str, required=True,
                        help='Directory containing validation results')
    parser.add_argument('--fail-on-error', action='store_true',
                        help='Exit with error code if validation failed')
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    exit_code = check_validation_status(results_dir, args.fail_on_error)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()