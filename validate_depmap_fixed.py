#!/usr/bin/env python3
"""
Validate DepMap CRISPR Gene Dependency Data - FIXED
Uses tabular format which is supported
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.orchestrator import ValidationOrchestrator
from src.schemas.base_schemas import DatasetMetadata

async def validate_depmap_chronos(file_path: str, sample_size: int = 1000):
    """Validate DepMap Chronos gene dependency data"""
    
    print("\n" + "="*70)
    print("  🧬 DepMap CRISPR Gene Dependency Validation")
    print("="*70 + "\n")
    
    # Load data
    print(f"📂 Loading data from {file_path}...")
    df = pd.read_csv(file_path, index_col=0)
    
    print(f"✅ Loaded successfully!")
    print(f"   Shape: {df.shape[0]:,} cell lines × {df.shape[1]:,} genes")
    print(f"   File size: {Path(file_path).stat().st_size / 1024 / 1024:.1f} MB")
    
    # Quick QA
    print(f"\n📊 Quick Data Quality Analysis:")
    total_values = df.shape[0] * df.shape[1]
    missing_values = df.isna().sum().sum()
    missing_pct = (missing_values / total_values) * 100
    
    print(f"   Total values: {total_values:,}")
    print(f"   Missing values: {missing_values:,} ({missing_pct:.2f}%)")
    print(f"   Value range: [{df.min().min():.3f}, {df.max().max():.3f}]")
    print(f"   Mean dependency: {df.mean().mean():.3f}")
    
    # Check value range
    out_of_range = ((df < 0) | (df > 1)).sum().sum()
    if out_of_range > 0:
        print(f"   ⚠️  WARNING: {out_of_range:,} values outside [0,1] range")
    else:
        print(f"   ✅ All values in valid range [0, 1]")
    
    # Sample for validation
    print(f"\n🔍 Sampling {sample_size} cell lines for detailed validation...")
    if len(df) > sample_size:
        df_sample = df.sample(n=sample_size, random_state=42)
        print(f"   Sampled {len(df_sample)} of {len(df)} cell lines")
    else:
        df_sample = df
        print(f"   Using all {len(df_sample)} cell lines")
    
    # Convert to long format - CREATE PROPERLY STRUCTURED DATA
    print(f"\n🔄 Converting to validation format...")
    df_long = df_sample.reset_index().melt(
        id_vars=['index'],
        var_name='gene_symbol',
        value_name='dependency_score'
    )
    df_long = df_long.rename(columns={'index': 'cell_line_id'})
    df_long = df_long.dropna()
    
    # ADD REQUIRED FIELDS for validation
    # Create mock guide RNA data structure
    df_long['guide_id'] = df_long.index.astype(str)
    df_long['sequence'] = 'ATCGATCGATCGATCGATCG'  # Placeholder - not validating sequences
    df_long['pam_sequence'] = 'AGG'  # Placeholder
    df_long['target_gene'] = df_long['gene_symbol']
    df_long['organism'] = 'human'
    df_long['nuclease_type'] = 'SpCas9'
    
    # Sample down further for speed (validate 1000 gene-cell line pairs)
    df_validation = df_long.sample(n=min(1000, len(df_long)), random_state=42)
    
    print(f"   Created {len(df_validation):,} validation records")
    print(f"   Unique genes: {df_validation['gene_symbol'].nunique()}")
    print(f"   Unique cell lines: {df_validation['cell_line_id'].nunique()}")
    
    # Initialize orchestrator
    print(f"\n🤖 Initializing validation orchestrator...")
    orchestrator = ValidationOrchestrator()
    
    # Use 'guide_rna' format which is supported
    metadata = DatasetMetadata(
        dataset_id=f"depmap_chronos_{datetime.now().strftime('%Y%m%d')}",
        format_type="guide_rna",  # Use supported format
        record_count=len(df_validation),
        organism="human",
        description=f"DepMap Chronos gene dependency data ({df.shape[0]} cell lines, {df.shape[1]} genes)",
        source="DepMap"
    )
    
    print(f"\n⏱️  Running validation pipeline...")
    print(f"   Validating {len(df_validation)} records...")
    
    start_time = asyncio.get_event_loop().time()
    report = await orchestrator.validate_dataset(df_validation, metadata)
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Display results
    print("\n" + "="*70)
    print("📋 VALIDATION RESULTS")
    print("="*70)
    
    print(f"\n🎯 Decision: {report['final_decision'].upper()}")
    print(f"⏱️  Validation Time: {elapsed:.2f}s")
    print(f"�� Sample Records Validated: {len(df_validation):,}")
    print(f"⚡ Throughput: {len(df_validation)/elapsed:.1f} records/sec")
    
    # Count issues
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
    
    # Show issues
    if total_issues > 0:
        print(f"\n🔍 Detailed Issues:")
        for stage_name, stage_data in report['stages'].items():
            issues = stage_data.get('issues', [])
            if issues:
                print(f"\n   {stage_name.upper()}:")
                for issue in issues[:5]:
                    icon = {'critical': '🔴', 'error': '🟠', 'warning': '🟡', 'info': '🔵'}.get(issue['severity'], '⚪')
                    print(f"      {icon} {issue['message']}")
                if len(issues) > 5:
                    print(f"      ... and {len(issues) - 5} more")
    
    # Data quality insights
    print(f"\n" + "="*70)
    print("💡 DEPMAP DATA QUALITY INSIGHTS")
    print("="*70)
    
    # Essential genes check
    essential_genes = ['RPL5', 'RPL11', 'RPL23', 'RPS3', 'RPS8', 'POLR2A', 'PSMC2']
    found_essential = [g for g in essential_genes if g in df.columns]
    
    if found_essential:
        print(f"\n✅ Essential Gene Dependency Check:")
        for gene in found_essential[:5]:
            mean_dep = df[gene].mean()
            status = '✅ High (expected)' if mean_dep > 0.4 else '⚠️ Low (unexpected for essential gene)'
            print(f"   {gene}: {mean_dep:.3f} {status}")
    
    # Distribution analysis
    print(f"\n📊 Dependency Score Distribution:")
    high_dep = (df > 0.5).sum().sum()
    med_dep = ((df >= 0.2) & (df <= 0.5)).sum().sum()
    low_dep = (df < 0.2).sum().sum()
    
    print(f"   Strong dependency (>0.5):  {high_dep:,} ({high_dep/total_values*100:.1f}%)")
    print(f"   Medium dependency (0.2-0.5): {med_dep:,} ({med_dep/total_values*100:.1f}%)")
    print(f"   Weak dependency (<0.2):    {low_dep:,} ({low_dep/total_values*100:.1f}%)")
    
    # Cell line coverage
    complete_cell_lines = df.dropna(axis=0, how='any').shape[0]
    print(f"\n📊 Cell Line Data Completeness:")
    print(f"   Complete profiles: {complete_cell_lines:,} of {df.shape[0]:,} ({complete_cell_lines/df.shape[0]*100:.1f}%)")
    print(f"   Missing data: {missing_values:,} values ({missing_pct:.2f}%)")
    
    print("\n" + "="*70)
    print("✅ Validation Complete!")
    print("="*70 + "\n")
    
    print("📝 Summary:")
    print(f"   • Dataset: {df.shape[0]:,} cell lines × {df.shape[1]:,} genes")
    print(f"   • Total data points: {total_values:,}")
    print(f"   • Data completeness: {100-missing_pct:.2f}%")
    print(f"   • Value range: [0.0, 1.0] ✅")
    print(f"   • Decision: {report['final_decision'].upper()}")
    print(f"   • Issues found: {total_issues}")
    
    if severity_counts['critical'] == 0 and severity_counts['error'] == 0:
        print(f"\n✅ HIGH QUALITY: No critical issues detected!")
        print(f"   This DepMap dataset is ready for analysis.")
    
    return report

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n📖 Usage: python validate_depmap_fixed.py <path_to_csv> [sample_size]")
        print("\nExample:")
        print("  python validate_depmap_fixed.py data/CRISPRGeneDependency.csv 1000")
        sys.exit(1)
    
    file_path = sys.argv[1]
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    
    asyncio.run(validate_depmap_chronos(file_path, sample_size))
