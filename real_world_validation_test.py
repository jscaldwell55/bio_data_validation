#!/usr/bin/env python3
"""
Real-World Validation Test
Demonstrates complete validation workflow with realistic data and report generation.

Usage: poetry run python real_world_validation_test.py
"""

import asyncio
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import DatasetMetadata


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_section(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'-'*80}{Colors.END}")


def create_realistic_dataset():
    """Create a realistic guide RNA dataset with various quality issues"""
    
    data = [
        # Perfect guides
        {
            "guide_id": "gRNA_001",
            "sequence": "ATCGATCGATCGATCGATCG",  # 20bp perfect
            "pam_sequence": "AGG",
            "target_gene": "BRCA1",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.92,
            "on_target_score": 0.88
        },
        {
            "guide_id": "gRNA_002",
            "sequence": "GCTAGCTAGCTAGCTAGCTA",
            "pam_sequence": "TGG",
            "target_gene": "TP53",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.89,
            "on_target_score": 0.91
        },
        
        # Suboptimal but usable
        {
            "guide_id": "gRNA_003",
            "sequence": "TACGTACGTACGTACGTACGTACG",  # 24bp - suboptimal length
            "pam_sequence": "CGG",
            "target_gene": "KRAS",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.75,
            "on_target_score": 0.82
        },
        
        # Has poly-T stretch (warning)
        {
            "guide_id": "gRNA_004",
            "sequence": "ATTTTTCGATCGATCGATCG",  # TTTT stretch
            "pam_sequence": "AGG",
            "target_gene": "MYC",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.68,
            "on_target_score": 0.71
        },
        
        # Low GC content (warning)
        {
            "guide_id": "gRNA_005",
            "sequence": "ATAATAATAATAATAATAAT",  # Very low GC
            "pam_sequence": "TGG",
            "target_gene": "EGFR",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.55,
            "on_target_score": 0.61
        },
        
        # Invalid PAM (error)
        {
            "guide_id": "gRNA_006",
            "sequence": "GCTAGCTAGCTAGCTAGCTA",
            "pam_sequence": "AAA",  # Invalid for SpCas9
            "target_gene": "PTEN",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.45,
            "on_target_score": 0.52
        },
        
        # Too short (error)
        {
            "guide_id": "gRNA_007",
            "sequence": "ATCGATCGATCG",  # Only 12bp - too short
            "pam_sequence": "AGG",
            "target_gene": "BRAF",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.32,
            "on_target_score": 0.41
        },
        
        # High quality guides
        {
            "guide_id": "gRNA_008",
            "sequence": "CGCGCGATATATATCGCGCG",
            "pam_sequence": "CGG",
            "target_gene": "PIK3CA",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.94,
            "on_target_score": 0.89
        },
        {
            "guide_id": "gRNA_009",
            "sequence": "TAGCTAGCTAGCTAGCTAGC",
            "pam_sequence": "TGG",
            "target_gene": "AKT1",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.87,
            "on_target_score": 0.93
        },
        {
            "guide_id": "gRNA_010",
            "sequence": "ATCGATCGATCGATCGATCG",
            "pam_sequence": "AGG",
            "target_gene": "NRAS",
            "organism": "human",
            "nuclease_type": "SpCas9",
            "efficiency_score": 0.91,
            "on_target_score": 0.88
        }
    ]
    
    return pd.DataFrame(data)


def print_dataset_summary(df: pd.DataFrame):
    """Print summary of the dataset"""
    print_section("Dataset Summary")
    
    print(f"Total guides: {Colors.BOLD}{len(df)}{Colors.END}")
    print(f"Columns: {', '.join(df.columns)}")
    print(f"\n{Colors.UNDERLINE}Guide length distribution:{Colors.END}")
    lengths = df['sequence'].str.len()
    print(f"  Min: {lengths.min()}bp")
    print(f"  Max: {lengths.max()}bp")
    print(f"  Mean: {lengths.mean():.1f}bp")
    print(f"  Median: {lengths.median():.0f}bp")
    
    print(f"\n{Colors.UNDERLINE}Efficiency score statistics:{Colors.END}")
    print(f"  Mean: {df['efficiency_score'].mean():.3f}")
    print(f"  Min: {df['efficiency_score'].min():.3f}")
    print(f"  Max: {df['efficiency_score'].max():.3f}")
    
    print(f"\n{Colors.UNDERLINE}Target genes:{Colors.END} {', '.join(df['target_gene'].unique())}")


def print_validation_report(report: dict):
    """Print comprehensive validation report"""
    
    print_section("Validation Results")
    
    # Overall decision
    decision = report['final_decision']
    decision_color = {
        'accepted': Colors.GREEN,
        'conditional_accept': Colors.YELLOW,
        'rejected': Colors.RED,
        'error': Colors.RED
    }.get(decision, Colors.YELLOW)
    
    print(f"Decision: {decision_color}{Colors.BOLD}{decision.upper()}{Colors.END}")
    print(f"Rationale: {report['decision_rationale']}")
    print(f"Execution time: {Colors.BOLD}{report['execution_time_seconds']:.2f}s{Colors.END}")
    print(f"Human review required: {Colors.BOLD}{report['requires_human_review']}{Colors.END}")
    print(f"Short-circuited: {report.get('short_circuited', False)}")
    
    # Stage-by-stage results
    print_section("Validation Stages")
    
    stages = report.get('stages', {})
    for stage_name, stage_data in stages.items():
        if stage_name == 'policy':
            continue  # Skip policy stage for now
            
        passed = stage_data.get('passed', True)
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
        
        severity = stage_data.get('severity', 'info')
        issue_count = len(stage_data.get('issues', []))
        
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}{stage_name.upper()}{Colors.END}")
        print(f"  Status: {status}")
        print(f"  Severity: {severity}")
        print(f"  Issues found: {issue_count}")
        print(f"  Execution time: {stage_data.get('execution_time_ms', 0):.1f}ms")
        print(f"  Records processed: {stage_data.get('records_processed', 'N/A')}")
        
        # Print issues
        issues = stage_data.get('issues', [])
        if issues:
            print(f"\n  {Colors.BOLD}Issues:{Colors.END}")
            for i, issue in enumerate(issues, 1):
                severity_str = issue.get('severity', 'info')
                severity_color = {
                    'critical': Colors.RED,
                    'error': Colors.RED,
                    'warning': Colors.YELLOW,
                    'info': Colors.BLUE
                }.get(severity_str, Colors.BLUE)
                
                msg = issue.get('message', 'No message')
                field = issue.get('field', 'unknown')
                rule_id = issue.get('rule_id', '')
                
                print(f"    {i}. [{severity_color}{severity_str.upper()}{Colors.END}] {msg}")
                if rule_id:
                    print(f"       Rule: {Colors.CYAN}{rule_id}{Colors.END}, Field: {Colors.CYAN}{field}{Colors.END}")


def print_severity_breakdown(report: dict):
    """Print breakdown of issues by severity"""
    print_section("Issue Severity Breakdown")
    
    policy_stage = report.get('stages', {}).get('policy', {})
    severity_counts = policy_stage.get('metadata', {}).get('severity_counts', {})
    
    if not severity_counts:
        print(f"{Colors.GREEN}✓ No issues detected!{Colors.END}")
        return
    
    # Create visual bar chart
    max_count = max(severity_counts.values()) if severity_counts else 0
    
    for severity, count in sorted(severity_counts.items()):
        if count == 0:
            continue
            
        color = {
            'critical': Colors.RED,
            'error': Colors.RED,
            'warning': Colors.YELLOW,
            'info': Colors.BLUE
        }.get(severity, Colors.BLUE)
        
        bar_length = int((count / max_count) * 40) if max_count > 0 else 0
        bar = '█' * bar_length
        empty = ' ' * (40 - bar_length)
        
        print(f"{severity.upper():10} [{color}{bar}{Colors.END}{empty}] {Colors.BOLD}{count}{Colors.END}")


def print_recommendations(report: dict):
    """Print actionable recommendations based on validation results"""
    print_section("Recommendations")
    
    decision = report['final_decision']
    severity_counts = report.get('stages', {}).get('policy', {}).get('metadata', {}).get('severity_counts', {})
    
    if decision == 'accepted':
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Dataset quality is excellent!{Colors.END}")
        print(f"  {Colors.GREEN}•{Colors.END} All critical validation checks passed")
        print(f"  {Colors.GREEN}•{Colors.END} Data is ready for downstream analysis")
        print(f"  {Colors.GREEN}•{Colors.END} Consider running production pipeline")
        
    elif decision == 'conditional_accept':
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Dataset has issues that require review:{Colors.END}")
        
        # Get conditions from policy
        policy_stage = report.get('stages', {}).get('policy', {})
        conditions = policy_stage.get('metadata', {}).get('conditions', [])
        
        # FIXED: Be specific about what needs review
        if severity_counts.get('error', 0) > 0:
            print(f"  {Colors.YELLOW}•{Colors.END} {severity_counts['error']} ERROR-level issues detected")
            print(f"  {Colors.YELLOW}•{Colors.END} Fix errors before production deployment")
        
        if severity_counts.get('warning', 0) > 0:
            print(f"  {Colors.YELLOW}•{Colors.END} {severity_counts['warning']} WARNING-level issues detected")
            print(f"  {Colors.YELLOW}•{Colors.END} Review warnings for potential optimization")
        
        if conditions:
            print(f"\n  {Colors.BOLD}Conditions:{Colors.END}")
            for condition in conditions:
                print(f"  {Colors.YELLOW}•{Colors.END} {condition}")
        
        print(f"\n  {Colors.YELLOW}→{Colors.END} Dataset may be usable after review and fixes")
        
    elif decision == 'rejected':
        print(f"{Colors.RED}{Colors.BOLD}✗ Dataset has critical issues - NOT RECOMMENDED for use:{Colors.END}")
        
        # FIXED: Be specific about why it's rejected
        if severity_counts.get('critical', 0) > 0:
            print(f"  {Colors.RED}•{Colors.END} {severity_counts['critical']} CRITICAL issue(s) detected")
        
        error_count = severity_counts.get('error', 0)
        error_threshold = 5  # Should match policy config
        
        if error_count >= error_threshold:
            print(f"  {Colors.RED}•{Colors.END} {error_count} errors exceed threshold ({error_threshold})")
        
        print(f"  {Colors.RED}•{Colors.END} Fix all critical/error-level issues before proceeding")
        print(f"  {Colors.RED}•{Colors.END} Review data collection and processing pipeline")
        print(f"  {Colors.RED}•{Colors.END} Consider re-generating dataset with corrections")
        
    else:  # error
        print(f"{Colors.RED}{Colors.BOLD}✗ Validation encountered a system error{Colors.END}")
        print(f"  {Colors.RED}•{Colors.END} Check validation logs for details")
        print(f"  {Colors.RED}•{Colors.END} Verify input data format")


def save_report_to_file(report: dict, df: pd.DataFrame, filename: str = "validation_report.json"):
    """Save validation report and data to files"""
    output_dir = Path("validation_output")
    output_dir.mkdir(exist_ok=True)
    
    # Save JSON report
    json_path = output_dir / filename
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Save CSV with validation flags
    csv_path = output_dir / filename.replace('.json', '_data.csv')
    df.to_csv(csv_path, index=False)
    
    # Create markdown summary
    md_path = output_dir / filename.replace('.json', '_summary.md')
    with open(md_path, 'w') as f:
        f.write(f"# Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Dataset ID:** {report['dataset_id']}\n")
        f.write(f"- **Decision:** {report['final_decision'].upper()}\n")
        f.write(f"- **Rationale:** {report['decision_rationale']}\n")
        f.write(f"- **Records:** {len(df)}\n")
        f.write(f"- **Execution Time:** {report['execution_time_seconds']:.2f}s\n")
        f.write(f"- **Short-circuited:** {report.get('short_circuited', False)}\n\n")
        
        # Add severity breakdown
        policy_stage = report.get('stages', {}).get('policy', {})
        severity_counts = policy_stage.get('metadata', {}).get('severity_counts', {})
        
        if severity_counts:
            f.write(f"## Issue Summary\n\n")
            for severity, count in severity_counts.items():
                if count > 0:
                    f.write(f"- **{severity.upper()}:** {count}\n")
        
        f.write(f"\n## Stages\n\n")
        for stage_name, stage_data in report.get('stages', {}).items():
            if stage_name == 'policy':
                continue
            f.write(f"### {stage_name.upper()}\n\n")
            f.write(f"- **Status:** {'✓ PASS' if stage_data.get('passed') else '✗ FAIL'}\n")
            f.write(f"- **Issues:** {len(stage_data.get('issues', []))}\n")
            f.write(f"- **Execution Time:** {stage_data.get('execution_time_ms', 0):.1f}ms\n\n")
            
            # Add issues to markdown
            issues = stage_data.get('issues', [])
            if issues:
                f.write(f"#### Issues\n\n")
                for i, issue in enumerate(issues, 1):
                    f.write(f"{i}. **[{issue.get('severity', 'info').upper()}]** {issue.get('message', 'No message')}\n")
                    if issue.get('rule_id'):
                        f.write(f"   - Rule: `{issue.get('rule_id')}`, Field: `{issue.get('field')}`\n")
                f.write("\n")
    
    print(f"\n{Colors.GREEN}✓ Report saved:{Colors.END}")
    print(f"  JSON: {Colors.CYAN}{json_path}{Colors.END}")
    print(f"  CSV: {Colors.CYAN}{csv_path}{Colors.END}")
    print(f"  Markdown: {Colors.CYAN}{md_path}{Colors.END}")


async def run_complete_validation():
    """Run complete validation workflow with real data"""
    
    print_header("REAL-WORLD VALIDATION TEST")
    print(f"{Colors.CYAN}Comprehensive guide RNA dataset validation{Colors.END}\n")
    
    # Step 1: Create realistic dataset
    print(f"{Colors.BOLD}Step 1: Creating realistic dataset...{Colors.END}")
    df = create_realistic_dataset()
    print(f"{Colors.GREEN}✓{Colors.END} Created dataset with {len(df)} guide RNAs")
    
    # Step 2: Display dataset summary
    print_dataset_summary(df)
    
    # Step 3: Set up validation orchestrator
    print(f"\n{Colors.BOLD}Step 2: Initializing validation orchestrator...{Colors.END}")
    config = OrchestrationConfig(
        timeout_seconds=300,
        enable_short_circuit=False,  # Run all checks for comprehensive report
        enable_parallel_bio=True
    )
    orchestrator = ValidationOrchestrator(config)
    print(f"{Colors.GREEN}✓{Colors.END} Orchestrator ready")
    
    # Step 4: Create metadata
    metadata = DatasetMetadata(
        dataset_id="CRISPR_SCREEN_2024_Q4",
        format_type="guide_rna",
        record_count=len(df),
        organism="human",
        experiment_type="guide_rna",
        source="in-house_design",
        additional_metadata={
            "project": "Cancer Target Validation",
            "researcher": "Dr. Smith",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "version": "1.0.0"
        }
    )
    
    # Step 5: Run validation
    print(f"\n{Colors.BOLD}Step 3: Running validation...{Colors.END}")
    print(f"{Colors.CYAN}This may take a few seconds...{Colors.END}\n")
    
    start_time = datetime.now()
    
    try:
        report = await orchestrator.validate_dataset(df, metadata)
        end_time = datetime.now()
        
        print(f"{Colors.GREEN}✓{Colors.END} Validation complete!")
        print(f"  Duration: {Colors.BOLD}{(end_time - start_time).total_seconds():.2f}s{Colors.END}")
        
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}ERROR during validation:{Colors.END} {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Step 6: Display comprehensive results
    print_validation_report(report)
    print_severity_breakdown(report)
    print_recommendations(report)
    
    # Step 7: Save report
    print_section("Saving Results")
    
    try:
        save_report_to_file(report, df, "crispr_validation_report.json")
    except Exception as e:
        print(f"{Colors.RED}✗ Error saving report:{Colors.END} {str(e)}")
        return 1
    
    # Step 8: Summary
    print_header("VALIDATION COMPLETE")
    
    decision = report['final_decision']
    if decision == 'accepted':
        print(f"{Colors.GREEN}{Colors.BOLD}✓ DATASET ACCEPTED{Colors.END}")
        print(f"{Colors.GREEN}The dataset meets all quality standards!{Colors.END}")
        return 0
    elif decision == 'conditional_accept':
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ CONDITIONAL ACCEPT{Colors.END}")
        print(f"{Colors.YELLOW}Review warnings before proceeding to production.{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ DATASET REJECTED{Colors.END}")
        print(f"{Colors.RED}Critical issues detected - dataset should not be used.{Colors.END}")
        return 1
    
def print_validation_report(report: dict):
    """Print comprehensive validation report"""
    
    print_section("Validation Results")
    
    # ADDED: Debug - show policy decision details
    policy_stage = report.get('stages', {}).get('policy', {})
    if 'metadata' in policy_stage:
        severity_counts = policy_stage['metadata'].get('severity_counts', {})
        policy_decision = policy_stage['metadata'].get('decision', 'unknown')
        
        print(f"\n{Colors.CYAN}[DEBUG] Policy Engine Output:{Colors.END}")
        print(f"  Severity counts: {severity_counts}")
        print(f"  Policy decision: {policy_decision}")
        print(f"  Final decision: {report['final_decision']}")
        print()
    
    # Overall decision
    decision = report['final_decision']
    decision_color = {
        'accepted': Colors.GREEN,
        'conditional_accept': Colors.YELLOW,
        'rejected': Colors.RED,
        'error': Colors.RED
    }.get(decision, Colors.YELLOW)
    
    # ADDED: Better decision display
    decision_display = decision.replace('_', ' ').upper()
    
    print(f"Decision: {decision_color}{Colors.BOLD}{decision_display}{Colors.END}")
    print(f"Rationale: {report['decision_rationale']}")
    print(f"Execution time: {Colors.BOLD}{report['execution_time_seconds']:.2f}s{Colors.END}")
    print(f"Human review required: {Colors.BOLD}{report['requires_human_review']}{Colors.END}")
    print(f"Short-circuited: {report.get('short_circuited', False)}")
    
    # ADDED: Show optimization stats if available
    bio_lookups_stage = report.get('stages', {}).get('bio_lookups', {})
    if 'metadata' in bio_lookups_stage:
        metadata = bio_lookups_stage['metadata']
        if 'api_calls_made' in metadata:
            print(f"\n{Colors.CYAN}Performance Metrics:{Colors.END}")
            print(f"  API calls made: {metadata.get('api_calls_made', 'N/A')}")
            print(f"  Genes validated: {metadata.get('genes_validated', 'N/A')}")
            print(f"  Optimization: {metadata.get('optimization', 'N/A')}")
            print(f"  Improvement: {metadata.get('performance_improvement', 'N/A')}")
    
    # [Rest of the function remains the same...]


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_complete_validation())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ Validation interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ FATAL ERROR:{Colors.END} {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)