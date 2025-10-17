#!/usr/bin/env python3
"""
Test script for rule versioning in validation reports.

Verifies:
1. Ruleset version is loaded from validation_rules.yml
2. Version metadata is included in validation reports
3. Hash is computed for reproducibility

Usage:
    python scripts/test_rule_versioning.py
"""

import asyncio
import pandas as pd
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import DatasetMetadata


async def test_rule_versioning():
    """Test that rule versioning is included in reports"""
    print("\n" + "="*70)
    print("TEST: Rule Versioning in Validation Reports")
    print("="*70)
    
    # Create test data
    test_data = pd.DataFrame({
        'guide_id': ['g1', 'g2'],
        'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
        'pam_sequence': ['AGG', 'TGG'],
        'target_gene': ['BRCA1', 'TP53'],
        'organism': ['human', 'human'],
        'nuclease_type': ['SpCas9', 'SpCas9']
    })
    
    # Initialize orchestrator
    config = OrchestrationConfig()
    orchestrator = ValidationOrchestrator(config)
    
    # Create metadata
    metadata = DatasetMetadata(
        dataset_id="test_versioning_001",
        format_type="guide_rna",
        record_count=len(test_data),
        organism="human"
    )
    
    print("\n--- Running Validation ---")
    
    # Run validation
    report = await orchestrator.validate_dataset(test_data, metadata)
    
    print("\n--- Checking Ruleset Metadata ---")
    
    # Check if ruleset_metadata is present
    if "ruleset_metadata" not in report:
        print("❌ FAILED: ruleset_metadata not found in report")
        return False
    
    ruleset = report["ruleset_metadata"]
    
    print(f"\n✅ Ruleset Metadata Found:")
    print(f"  Version: {ruleset.get('version')}")
    print(f"  Last Updated: {ruleset.get('last_updated')}")
    print(f"  Source: {ruleset.get('source')}")
    print(f"  Hash: {ruleset.get('hash')}")
    
    if ruleset.get('latest_changes'):
        print(f"\n  Latest Changes:")
        for change in ruleset['latest_changes'][:3]:
            print(f"    - {change}")
    
    # Verify critical fields
    checks = {
        "Version is present": ruleset.get('version') != 'unknown',
        "Hash is computed": ruleset.get('hash') is not None,
        "Source is tracked": ruleset.get('source') != 'unknown'
    }
    
    print(f"\n--- Validation Checks ---")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    # Check API configuration also included
    if "api_configuration" in report:
        api_config = report["api_configuration"]
        print(f"\n--- API Configuration (also tracked) ---")
        print(f"  NCBI API Key: {'✅' if api_config.get('ncbi_api_key_configured') else '❌'}")
        print(f"  Rate Limit: {api_config.get('ncbi_rate_limit')}")
        print(f"  Cache Enabled: {'✅' if api_config.get('cache_enabled') else '❌'}")
        print(f"  Ensembl Fallback: {'✅' if api_config.get('ensembl_fallback_enabled') else '❌'}")
    
    # Save example report
    output_dir = Path("validation_output")
    output_dir.mkdir(exist_ok=True)
    
    report_path = output_dir / "example_report_with_versioning.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Example report saved: {report_path}")
    
    # Show sample of report structure
    print(f"\n--- Sample Report Structure ---")
    print(json.dumps({
        "validation_id": report["validation_id"],
        "dataset_id": report["dataset_id"],
        "final_decision": report["final_decision"],
        "ruleset_metadata": ruleset,
        "api_configuration": report.get("api_configuration", {}),
        "execution_time_seconds": report["execution_time_seconds"]
    }, indent=2))
    
    return all_passed


async def test_reproducibility():
    """Test that hash enables reproducibility tracking"""
    print("\n" + "="*70)
    print("TEST: Reproducibility via Hash Tracking")
    print("="*70)
    
    # Run same validation twice
    test_data = pd.DataFrame({
        'guide_id': ['g1'],
        'sequence': ['ATCGATCGATCGATCGATCG'],
        'pam_sequence': ['AGG'],
        'target_gene': ['BRCA1'],
        'organism': ['human'],
        'nuclease_type': ['SpCas9']
    })
    
    orchestrator = ValidationOrchestrator()
    metadata = DatasetMetadata(
        dataset_id="reproducibility_test",
        format_type="guide_rna",
        record_count=1
    )
    
    # First run
    report1 = await orchestrator.validate_dataset(test_data, metadata)
    hash1 = report1["ruleset_metadata"]["hash"]
    
    # Second run
    report2 = await orchestrator.validate_dataset(test_data, metadata)
    hash2 = report2["ruleset_metadata"]["hash"]
    
    print(f"\n--- Hash Comparison ---")
    print(f"  Run 1 Hash: {hash1}")
    print(f"  Run 2 Hash: {hash2}")
    
    if hash1 == hash2:
        print(f"  ✅ Hashes match - same ruleset used")
        reproducible = True
    else:
        print(f"  ❌ Hashes differ - ruleset changed between runs")
        reproducible = False
    
    print(f"\n--- Reproducibility ---")
    if reproducible:
        print("  ✅ Validation is reproducible with same ruleset version")
    else:
        print("  ⚠️  Ruleset changed - results may differ")
    
    return reproducible


async def main():
    """Run all tests"""
    print("\n" + "🧪 " * 35)
    print(" RULE VERSIONING TEST SUITE")
    print("🧪 " * 35)
    
    try:
        # Test 1: Rule versioning in reports
        versioning_passed = await test_rule_versioning()
        
        # Test 2: Reproducibility tracking
        reproducibility_passed = await test_reproducibility()
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        if versioning_passed:
            print("\n✅ Rule Versioning: PASSED")
        else:
            print("\n❌ Rule Versioning: FAILED")
        
        if reproducibility_passed:
            print("✅ Reproducibility Tracking: PASSED")
        else:
            print("❌ Reproducibility Tracking: FAILED")
        
        if versioning_passed and reproducibility_passed:
            print("\n" + "🎉 " * 35)
            print(" ALL TESTS PASSED!")
            print("🎉 " * 35)
            
            print("\n📋 Benefits:")
            print("  - Full reproducibility tracking")
            print("  - Ruleset changes auditable")
            print("  - Reports include version context")
            print("  - Hash enables integrity verification")
            return 0
        else:
            print("\n❌ Some tests failed")
            return 1
    
    except Exception as e:
        print(f"\n❌ Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)