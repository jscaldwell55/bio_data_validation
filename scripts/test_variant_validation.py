"""Test script for variant annotation validation."""

import asyncio
import pandas as pd
from src.validators.variant_validator import VariantValidator
from src.schemas.base_schemas import ValidationSeverity

async def main():
    print("=" * 60)
    print("Testing Variant Annotation Validator")
    print("=" * 60)
    
    # Load test data
    df = pd.read_csv('data/test_variants/sample_variants.csv')
    print(f"\nLoaded {len(df)} test variants")
    print(df.head())
    
    # Initialize validator
    validator = VariantValidator(reference_genome="GRCh38")
    
    # Run validation
    print("\n" + "=" * 60)
    print("Running validation...")
    print("=" * 60)
    
    issues = validator.validate(df)
    
    # Report results
    print(f"\nFound {len(issues)} issues:\n")
    
    for severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR, 
                     ValidationSeverity.WARNING, ValidationSeverity.INFO]:
        severity_issues = [i for i in issues if i.severity == severity]
        if severity_issues:
            print(f"\n{severity.value.upper()} ({len(severity_issues)}):")
            for issue in severity_issues:
                print(f"  - {issue.message}")
                # FIX: Use the correct attribute name
                affected = getattr(issue, 'affected_records', None) or \
                          getattr(issue, 'affected_count', None) or \
                          getattr(issue, 'record_count', None) or 0
                if affected > 0:
                    print(f"    Affected: {affected} records")
    
    if not issues:
        print("✅ All validation checks passed!")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())