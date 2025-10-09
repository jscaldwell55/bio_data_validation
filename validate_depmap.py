#!/usr/bin/env python3
"""
Validate DepMap CRISPR Gene Dependency Data
Handles wide-format dependency matrices
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Add project to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.orchestrator import ValidationOrchestrator
from src.schemas.base_schemas import DatasetMetadata

async def validate_depmap_chronos(file_path: str, sample_size: int = 1000):
    """
    Validate DepMap Chronos gene dependency data
    
    Args:
        file_path: Path to CRISPRGeneDependency.csv
        sample_size: Number of cell lines to validate (for speed)
    """
    
    print("\n" + "="*70)
    print("  🧬 DepMap CRISPR Gene Dependency Validation")
    print("="*70 + "\n")
    
    # 1. Load data
    print(f"📂 Loading data from {file_path}...")
    df = pd.read_csv(file_path, index_col=0)
    
    print(f"✅ Loaded successfully!")
    print(f"   Shape: {df.shape[0]:,} cell lines × {df.shape[1]:,} genes")
    print(f"   File size: {Path(file_path).stat().st_size / 1024 / 1024:.1f} MB")
    
    # 2. Basic data quality checks (fast)
    print(f"\n📊 Quick Data Quality Analysis:")
    
    total_values = df.shape[0] * df.shape[1]
    missing_values = df.isna().sum().sum()
    missing_pct = (missing_values / total_values) * 100
    
    print(f"   Total values: {total_values:,}")
    print(f"   Missing values: {missing_values:,} ({missing_pct:.2f}%)")
    print(f"   Value range: [{df.min().min():.3f}, {df.max().max():.3f}]")
    print(f"   Mean dependency: {df.mean().mean():.3f}")
    
    # Check if values are in expected range [0, 1]
    out_of_range = ((df < 0) | (df > 1)).sum().sum()
    if out_of_range > 0:
        print(f"   ⚠️  WARNING: {out_of_range:,} values outside [0,1] range")
    else:
        print(f"   ✅ All values in valid range [0, 1]")
    
    # 3. Sample for detailed validation
    print(f"\n🔍 Sampling {sample_size} cell lines for detailed validation...")
    
    if len(df) > sample_size:
        df_sample = df.sample(n=sample_size, random_state=42)
        print(f"   Sampled {len(df_sample)} of {len(df)} cell lines")
    else:
        df_sample = df
        print(f"   Using all {len(df_sample)} cell lines")
    
    # 4. Convert to long format for validation
    print(f"\n🔄 Converting to long format for validation...")
    df_long = df_sample.reset_index().melt(
        id_vars=['index'],
        var_name='gene_symbol',
        value_name='dependency_score'
    )
    df_long = df_long.rename(columns={'index': 'cell_line_id'})
    
    # Remove missing values for validation
    df_long = df_long.dropna()
    
    print(f"   Converted to {len(df_long):,} records")
    print(f"   Unique genes: {df_long['gene_symbol'].nunique():,}")
    print(f"   Unique cell lines: {df_long['cell_line_id'].nunique():,}")
    
    # 5. Gene symbol validation (sample)
    print(f"\n🧬 Extracting gene symbols for NCBI validation...")
    unique_genes = df.columns.tolist()[:100]  # Sample first 100 genes
    print(f"   Will validate {len(unique_genes)} gene symbols against NCBI")
    
    # 6. Run validation
    print(f"\n🤖 Initializing validation orchestrator...")
    orchestrator = ValidationOrchestrator()
    
    metadata = DatasetMetadata(
        dataset_id=f"depmap_chronos_{datetime.now().strftime('%Y%m%d')}",
        format_type="crispr_dependency",
        record_count=len(df_long),
        organism="human",
        description=f"DepMap Chronos gene dependency data ({df.shape[0]} cell lines, {df.shape[1]} genes)",
        source="DepMap"
    )
    
    print(f"\n⏱️  Running validation pipeline...")
    print(f"   This may take 30-60 seconds due to NCBI API calls...")
    
    start_time = asyncio.get_event_loop().time()
    report = await orchestrator.validate_dataset(df_long, metadata)
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # 7. Display results
    print("\n" + "="*70)
    print("📋 VALIDATION RESULTS")
    print("="*70)
    
    print(f"\n🎯 Decision: {report['final_decision'].upper()}")
    print(f"⏱️  Validation Time: {elapsed:.2f}s")
    print(f"📊 Records Validated: {len(df_long):,}")
    print(f"⚡ Throughput: {len(df_long)/elapsed:.1f} records/sec")
    
    # Count issues by severity
    severity_counts = {'critical': 0, 'error': 0, 'warning': 0, 'info': 0}
    for stage_data in report['stages'].values():
        for issue in stage_data.get('issues', []):
            severity_counts[issue['severity']] += 1
    
    total_issues = sum(severity_counts.values())
    
    print(f"\n📌 Issues Summary:")
    print(f"   🔴 Critical: {severity_counts['critical']}")
    print(f"   🟠 Errors:   {severity_counts['error']}")
    print(f"   🟡 Warnings: {severity_counts['warning']}")
    print(f"   🔵 Info:     {severity_counts['info']}")
    print(f"   Total:      {total_issues}")
    
    # Show detailed issues
    if total_issues > 0:
        print(f"\n🔍 Detailed Issues:")
        for stage_name, stage_data in report['stages'].items():
            issues = stage_data.get('issues', [])
            if issues:
                print(f"\n   {stage_name.upper()}:")
                for issue in issues[:5]:  # Show first 5
                    icon = {'critical': '🔴', 'error': '🟠', 'warning': '🟡', 'info': '🔵'}.get(issue['severity'], '⚪')
                    print(f"      {icon} {issue['message']}")
                if len(issues) > 5:
                    print(f"      ... and {len(issues) - 5} more")
    
    # 8. Data quality insights
    print(f"\n" + "="*70)
    print("💡 DATA QUALITY INSIGHTS")
    print("="*70)
    
    # Check for essential genes (should have high dependency scores)
    essential_genes = ['RPL5', 'RPL11', 'RPL23', 'RPS3', 'RPS8']  # Known essential ribosomal proteins
    found_essential = [g for g in essential_genes if g in df.columns]
    
    if found_essential:
        print(f"\n✅ Essential Gene Check:")
        for gene in found_essential[:3]:
            mean_dep = df[gene].mean()
            print(f"   {gene}: Mean dependency = {mean_dep:.3f} {'✅ High (expected)' if mean_dep > 0.5 else '⚠️ Low (unexpected)'}")
    
    # Check for non-essential genes (should have low dependency)
    print(f"\n📊 Dependency Distribution:")
    print(f"   High dependency (>0.5): {(df > 0.5).sum().sum():,} values ({((df > 0.5).sum().sum() / total_values * 100):.1f}%)")
    print(f"   Low dependency (<0.2): {(df < 0.2).sum().sum():,} values ({((df < 0.2).sum().sum() / total_values * 100):.1f}%)")
    
    print("\n" + "="*70)
    print("✅ Validation Complete!")
    print("="*70 + "\n")
    
    # Save summary
    summary_file = f"depmap_validation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(summary_file, 'w') as f:
        f.write(f"DepMap CRISPR Validation Summary\n")
        f.write(f"================================\n\n")
        f.write(f"File: {file_path}\n")
        f.write(f"Shape: {df.shape[0]} cell lines × {df.shape[1]} genes\n")
        f.write(f"Decision: {report['final_decision']}\n")
        f.write(f"Issues: {total_issues}\n")
    
    print(f"📄 Summary saved to: {summary_file}")
    
    return report

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("\n📖 Usage: python validate_depmap.py <path_to_csv> [sample_size]")
        print("\nExample:")
        print("  python validate_depmap.py data/CRISPRGeneDependency.csv 1000")
        print("\nOptions:")
        print("  sample_size: Number of cell lines to validate (default: 1000)")
        print("               Use smaller number for faster validation")
        print("               Use 'all' to validate entire dataset (slow!)")
        sys.exit(1)
    
    file_path = sys.argv[1]
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != 'all' else 1000
    
    asyncio.run(validate_depmap_chronos(file_path, sample_size))
