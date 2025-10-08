# scripts/validation/generate_report.py
"""
Generate human-readable validation report.
"""
import argparse
from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict


def generate_markdown_report(results_dir: Path) -> str:
    """
    Generate markdown report from validation results.
    
    Args:
        results_dir: Directory containing validation results
        
    Returns:
        Markdown report string
    """
    # Load summary
    summary_path = results_dir / 'validation_summary.json'
    if not summary_path.exists():
        return "# Error: No validation summary found"
    
    with open(summary_path, 'r') as f:
        summary = json.load(f)
    
    # Load individual reports
    report_files = list(results_dir.glob('*_report.json'))
    reports = []
    for report_file in report_files:
        with open(report_file, 'r') as f:
            reports.append(json.load(f))
    
    # Generate markdown
    md = []
    md.append("# Data Validation Report")
    md.append(f"\n**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    # Summary section
    md.append("## Summary")
    md.append("")
    md.append(f"- **Total Datasets:** {summary['total_datasets']}")
    md.append(f"- **✅ Accepted:** {summary['accepted']}")
    md.append(f"- **⚠️ Conditional Accept:** {summary['conditional']}")
    md.append(f"- **❌ Rejected:** {summary['rejected']}")
    md.append(f"- **🔴 Errors:** {summary['errors']}")
    
    success_rate = (summary['accepted'] + summary['conditional']) / summary['total_datasets'] * 100
    md.append(f"- **Success Rate:** {success_rate:.1f}%")
    md.append("")
    
    # Detailed results
    md.append("## Detailed Results")
    md.append("")
    
    for report in reports:
        dataset_id = report.get('dataset_id', 'Unknown')
        decision = report.get('final_decision', 'UNKNOWN')
        
        # Decision icon
        icon = {
            'ACCEPTED': '✅',
            'CONDITIONAL_ACCEPT': '⚠️',
            'REJECTED': '❌',
            'ERROR': '🔴'
        }.get(decision, '❓')
        
        md.append(f"### {icon} {dataset_id}")
        md.append("")
        md.append(f"**Decision:** {decision}")
        md.append(f"**Execution Time:** {report.get('execution_time_seconds', 0):.2f}s")
        
        if report.get('requires_human_review'):
            md.append("**⚠️ Requires Human Review**")
        
        md.append("")
        
        # Issues by stage
        stages = report.get('stages', {})
        total_issues = sum(len(s.get('issues', [])) for s in stages.values())
        
        if total_issues > 0:
            md.append(f"**Issues Found:** {total_issues}")
            md.append("")
            
            for stage_name, stage_data in stages.items():
                issues = stage_data.get('issues', [])
                if issues:
                    md.append(f"#### {stage_name.title()} Stage")
                    md.append("")
                    
                    for issue in issues[:5]:  # Limit to first 5 per stage
                        severity = issue.get('severity', 'info').upper()
                        field = issue.get('field', 'N/A')
                        message = issue.get('message', 'No message')
                        
                        severity_icon = {
                            'CRITICAL': '🔴',
                            'ERROR': '❌',
                            'WARNING': '⚠️',
                            'INFO': 'ℹ️'
                        }.get(severity, '•')
                        
                        md.append(f"- {severity_icon} **[{severity}]** `{field}`: {message}")
                    
                    if len(issues) > 5:
                        md.append(f"- *(and {len(issues) - 5} more issues)*")
                    
                    md.append("")
        else:
            md.append("**No issues found** ✨")
            md.append("")
        
        md.append("---")
        md.append("")
    
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description='Generate validation report')
    parser.add_argument('--results-dir', type=str, required=True,
                        help='Directory containing validation results')
    parser.add_argument('--output', type=str, default='validation_report.md',
                        help='Output file path')
    parser.add_argument('--format', type=str, default='markdown',
                        choices=['markdown', 'html'],
                        help='Report format')
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    
    if args.format == 'markdown':
        report = generate_markdown_report(results_dir)
        
        # Save report
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            f.write(report)
        
        print(f"Report generated: {output_path}")
        print("\n" + "="*60)
        print(report)
        print("="*60)


if __name__ == "__main__":
    main()