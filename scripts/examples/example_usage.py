# scripts/examples/example_usage.py
"""
Example usage of the validation system.
"""
import asyncio
import pandas as pd
from pathlib import Path

from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import DatasetMetadata


async def example_guide_rna_validation():
    """Example: Validate guide RNA dataset"""
    print("="*60)
    print("Example 1: Guide RNA Validation")
    print("="*60)
    
    # Create sample data
    df = pd.DataFrame([
        {
            'guide_id': 'gRNA_001',
            'sequence': 'ATCGATCGATCGATCGATCG',
            'pam_sequence': 'AGG',
            'target_gene': 'BRCA1',
            'organism': 'human',
            'nuclease_type': 'SpCas9',
            'efficiency_score': 0.85
        },
        {
            'guide_id': 'gRNA_002',
            'sequence': 'GCTAGCTAGCTAGCTAGCTA',
            'pam_sequence': 'TGG',
            'target_gene': 'TP53',
            'organism': 'human',
            'nuclease_type': 'SpCas9',
            'efficiency_score': 0.72
        }
    ])
    
    # Setup orchestrator
    config = OrchestrationConfig(
        timeout_seconds=300,
        enable_short_circuit=True,
        enable_parallel_bio=True
    )
    orchestrator = ValidationOrchestrator(config)
    
    # Create metadata
    metadata = DatasetMetadata(
        dataset_id="example_001",
        format_type="guide_rna",
        record_count=len(df),
        organism="human",
        experiment_type="guide_rna"
    )
    
    # Validate
    report = await orchestrator.validate_dataset(df, metadata)
    
    # Print results
    print(f"\nValidation Results:")
    print(f"  Decision: {report['final_decision']}")
    print(f"  Time: {report['execution_time_seconds']:.2f}s")
    print(f"  Human Review Required: {report['requires_human_review']}")
    
    # Print issues
    total_issues = sum(
        len(stage['issues']) 
        for stage in report['stages'].values()
    )
    print(f"  Total Issues: {total_issues}")
    
    for stage_name, stage_data in report['stages'].items():
        if stage_data['issues']:
            print(f"\n  {stage_name.upper()} Issues:")
            for issue in stage_data['issues'][:3]:
                print(f"    - [{issue['severity']}] {issue['message']}")


async def example_fasta_validation():
    """Example: Validate FASTA file"""
    print("\n" + "="*60)
    print("Example 2: FASTA Validation")
    print("="*60)
    
    fasta_data = """>seq1 Test sequence 1
ATCGATCGATCGATCGATCG
>seq2 Test sequence 2
GCTAGCTAGCTAGCTAGCTA
"""
    
    config = OrchestrationConfig()
    orchestrator = ValidationOrchestrator(config)
    
    metadata = DatasetMetadata(
        dataset_id="example_fasta",
        format_type="fasta",
        record_count=2
    )
    
    report = await orchestrator.validate_dataset(fasta_data, metadata)
    
    print(f"\nValidation Results:")
    print(f"  Decision: {report['final_decision']}")
    print(f"  Records Validated: {report['stages']['schema']['records_processed']}")


async def main():
    """Run all examples"""
    await example_guide_rna_validation()
    await example_fasta_validation()
    
    print("\n" + "="*60)
    print("Examples Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())