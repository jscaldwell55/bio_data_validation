"""
Dataset Validation Script
Validates biological datasets using the multi-agent validation system
"""

import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from src.agents.orchestrator import ValidationOrchestrator
from src.schemas.base_schemas import DatasetMetadata, FormatType


async def validate_guide_rna_csv(filepath: str):
    """Validate a CSV file containing guide RNA data"""
    
    # Load data
    df = pd.read_csv(filepath)
    print(f"📁 Loaded {len(df)} records from {filepath}")
    
    # Create metadata
    metadata = DatasetMetadata(
        dataset_id=f"guide_rna_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        format_type=FormatType.GUIDE_RNA,
        record_count=len(df),
        organism="human",
        source_file=filepath
    )
    
    # Initialize orchestrator
    orchestrator = ValidationOrchestrator()
    
    # Run validation
    print("\n🔍 Starting validation...")
    report = await orchestrator.validate_dataset(df, metadata)
    
    # Display results
    print("\n" + "="*60)
    print("📊 VALIDATION RESULTS")
    print("="*60)
    print(f"Decision: {report['final_decision'].upper()}")
    print(f"Execution Time: {report['execution_time_seconds']:.2f}s")
    print(f"Requires Review: {report['requires_human_review']}")
    
    # Show severity breakdown
    severity_counts = report['stages']['policy']['severity_counts']
    print(f"\nIssue Breakdown:")
    print(f"  🚨 Critical: {severity_counts['critical']}")
    print(f"  ❌ Errors:   {severity_counts['error']}")
    print(f"  ⚠️  Warnings: {severity_counts['warning']}")
    print(f"  ℹ️  Info:     {severity_counts['info']}")
    
    # Show issues by stage
    print("\n📋 Issues by Stage:")
    for stage_name, stage_data in report['stages'].items():
        if stage_name == 'policy':
            continue
        issues = stage_data.get('issues', [])
        if issues:
            print(f"\n  {stage_name.upper()}:")
            for issue in issues[:5]:  # Show first 5
                print(f"    [{issue['severity']}] {issue['message']}")
            if len(issues) > 5:
                print(f"    ... and {len(issues) - 5} more")
    
    return report


async def validate_variant_annotation_csv(filepath: str):
    """Validate a CSV file containing variant annotation data"""
    
    df = pd.read_csv(filepath)
    print(f"📁 Loaded {len(df)} variants from {filepath}")
    
    metadata = DatasetMetadata(
        dataset_id=f"variants_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        format_type=FormatType.VARIANT_ANNOTATION,
        record_count=len(df),
        reference_genome="GRCh38",
        source_file=filepath
    )
    
    orchestrator = ValidationOrchestrator()
    
    print("\n🔍 Starting variant validation...")
    report = await orchestrator.validate_dataset(df, metadata)
    
    print("\n" + "="*60)
    print(f"Decision: {report['final_decision'].upper()}")
    print(f"Time: {report['execution_time_seconds']:.2f}s")
    
    return report


async def validate_sample_metadata_csv(filepath: str):
    """Validate a CSV file containing sample metadata"""
    
    df = pd.read_csv(filepath)
    print(f"📁 Loaded {len(df)} samples from {filepath}")
    
    metadata = DatasetMetadata(
        dataset_id=f"samples_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        format_type=FormatType.SAMPLE_METADATA,
        record_count=len(df),
        experiment_type="RNA-seq",
        source_file=filepath
    )
    
    orchestrator = ValidationOrchestrator()
    
    print("\n🔍 Starting sample metadata validation...")
    report = await orchestrator.validate_dataset(df, metadata)
    
    print("\n" + "="*60)
    print(f"Decision: {report['final_decision'].upper()}")
    print(f"Time: {report['execution_time_seconds']:.2f}s")
    
    return report


async def validate_from_dataframe():
    """Example: Create and validate data directly from a DataFrame"""
    
    # Create sample guide RNA data
    data = {
        'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
        'sequence': [
            'ATCGATCGATCGATCGATCG',  # 20bp
            'GCTAGCTAGCTAGCTAGCTA',  # 20bp
            'TTTTTTTTTTTTTTTTTTTT'   # 20bp, all T's (will trigger warning)
        ],
        'pam_sequence': ['AGG', 'TGG', 'CGG'],
        'target_gene': ['BRCA1', 'TP53', 'EGFR'],
        'organism': ['human', 'human', 'human'],
        'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9']
    }
    
    df = pd.DataFrame(data)
    print("📊 Created DataFrame with 3 guide RNAs")
    
    metadata = DatasetMetadata(
        dataset_id="test_guides",
        format_type=FormatType.GUIDE_RNA,
        record_count=len(df),
        organism="human"
    )
    
    orchestrator = ValidationOrchestrator()
    report = await orchestrator.validate_dataset(df, metadata)
    
    print(f"\n✅ Decision: {report['final_decision']}")
    
    return report


async def batch_validate_multiple_files(filepaths: list, format_type: str):
    """Validate multiple files in batch"""
    
    orchestrator = ValidationOrchestrator()
    results = []
    
    for filepath in filepaths:
        print(f"\n{'='*60}")
        print(f"Processing: {filepath}")
        print('='*60)
        
        df = pd.read_csv(filepath)
        
        metadata = DatasetMetadata(
            dataset_id=Path(filepath).stem,
            format_type=FormatType(format_type),
            record_count=len(df),
            source_file=filepath
        )
        
        report = await orchestrator.validate_dataset(df, metadata)
        results.append({
            'file': filepath,
            'decision': report['final_decision'],
            'time': report['execution_time_seconds']
        })
    
    # Summary
    print("\n" + "="*60)
    print("📊 BATCH VALIDATION SUMMARY")
    print("="*60)
    for result in results:
        status_icon = "✅" if result['decision'] == 'accepted' else "❌"
        print(f"{status_icon} {result['file']}: {result['decision'].upper()} ({result['time']:.2f}s)")
    
    return results


# Main execution examples
if __name__ == "__main__":
    
    # Example 1: Validate a guide RNA CSV file
    print("\n🧬 EXAMPLE 1: Validate Guide RNA CSV")
    asyncio.run(validate_guide_rna_csv("data/my_guides.csv"))
    
    # Example 2: Validate variant annotation data
    print("\n\n🧬 EXAMPLE 2: Validate Variant Annotations")
    # asyncio.run(validate_variant_annotation_csv("data/my_variants.csv"))
    
    # Example 3: Validate sample metadata
    print("\n\n🧬 EXAMPLE 3: Validate Sample Metadata")
    # asyncio.run(validate_sample_metadata_csv("data/my_samples.csv"))
    
    # Example 4: Create and validate DataFrame directly
    print("\n\n🧬 EXAMPLE 4: Validate In-Memory DataFrame")
    # asyncio.run(validate_from_dataframe())
    
    # Example 5: Batch validate multiple files
    print("\n\n🧬 EXAMPLE 5: Batch Validation")
    # files = ["data/batch1.csv", "data/batch2.csv", "data/batch3.csv"]
    # asyncio.run(batch_validate_multiple_files(files, "guide_rna"))