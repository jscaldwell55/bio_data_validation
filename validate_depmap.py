import asyncio
import pandas as pd
import numpy as np
from pathlib import Path
from src.validators.bio_lookups import BioLookupsValidator

async def validate_depmap_crispr_data():
    """
    Validate DepMap Achilles CRISPR gene effect scores
    Direct gene validation without using GUIDE_RNA format
    """
    
    # ========================================
    # STEP 1: LOAD DATA
    # ========================================
    csv_path = "/Users/jaycaldwell/Desktop/Achilles_gene_effect.csv"
    
    print("📂 Loading DepMap data...")
    df = pd.read_csv(csv_path, index_col=0)
    
    print("🔄 Converting data to numeric format...")
    df = df.apply(pd.to_numeric, errors='coerce')
    
    print(f"✅ Loaded: {df.shape[0]} genes × {df.shape[1]} cell lines")
    
    try:
        data_min = df.min().min()
        data_max = df.max().max()
        print(f"📊 Data range: {data_min:.3f} to {data_max:.3f}")
    except:
        print("⚠️  WARNING: Could not compute data range")
    
    print(f"📋 First few genes: {list(df.index[:5])}")
    print(f"📋 First few cell lines: {list(df.columns[:5])}")
    
    # ========================================
    # STEP 2: DATA QUALITY CHECKS
    # ========================================
    print("\n🔍 Running DepMap-specific quality checks...")
    
    issues = []
    
    # Check 1: Missing values
    missing_pct = (df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100
    if missing_pct > 5:
        issues.append(f"⚠️  WARNING: {missing_pct:.1f}% missing values in dataset")
    else:
        print(f"✅ Missing values: {missing_pct:.2f}% (acceptable)")
    
    # Check 2: Gene symbol format
    invalid_genes = [g for g in df.index if not isinstance(g, str) or len(g) < 2]
    if invalid_genes:
        issues.append(f"❌ ERROR: {len(invalid_genes)} invalid gene symbols")
        print(f"   Examples: {invalid_genes[:5]}")
    else:
        print(f"✅ All {len(df.index)} gene symbols have valid format")
    
    # Check 3: Cell line naming
    depmap_pattern = all('_' in str(col) for col in df.columns[:100])
    if depmap_pattern:
        print(f"✅ Cell line names follow DepMap convention")
    else:
        issues.append(f"⚠️  WARNING: Cell line naming may not follow standard DepMap format")
    
    # Check 4: Effect score distribution
    try:
        median_effect = df.median(axis=None, skipna=True)
        if abs(median_effect) > 0.1:
            issues.append(f"⚠️  WARNING: Median effect score {median_effect:.3f} (expected ~0)")
        else:
            print(f"✅ Effect score distribution centered at {median_effect:.3f}")
    except:
        median_effect = None
        print("⚠️  Could not compute median")
    
    # Check 5: Essential vs non-essential genes
    try:
        gene_medians = df.median(axis=1, skipna=True)
        strong_negative = (gene_medians < -0.5).sum()
        strong_positive = (gene_medians > 0.5).sum()
        print(f"✅ Found {strong_negative} likely essential genes (median < -0.5)")
        print(f"✅ Found {strong_positive} genes with positive effects (median > 0.5)")
    except:
        print("⚠️  Could not analyze gene essentiality")
    
    # Check 6: Outliers
    try:
        extreme_values = (df.abs() > 3).sum().sum()
        if extreme_values > 0:
            issues.append(f"⚠️  WARNING: {extreme_values} extreme values (|score| > 3)")
        else:
            print(f"✅ No extreme outliers detected (|score| < 3)")
    except:
        print("⚠️  Could not check for outliers")
    
    # ========================================
    # STEP 3: VALIDATE GENE SYMBOLS
    # ========================================
    print("\n🧬 Validating gene symbols against NCBI/Ensembl...")
    print(f"   Processing {len(df.index)} genes...")
    print("   ⏱️  First run: ~2-5 minutes (building cache)")
    print("   ⏱️  Subsequent runs: ~5-30 seconds (using cache)")
    
    # Create validator
    validator = BioLookupsValidator()
    
    # Prepare data for validation - create DataFrame with required columns
    gene_data = pd.DataFrame({
        'target_gene': df.index,
        'organism': ['human'] * len(df.index),
        'sequence': ['NNNNNNNNNNNNNNNNNNNN'] * len(df.index),  # Dummy sequence
        'pam_sequence': ['NGG'] * len(df.index),  # Dummy PAM
        'nuclease_type': ['SpCas9'] * len(df.index)  # Dummy nuclease
    })
    
    # Run validation using validate() method
    validation_result = await validator.validate(gene_data)
    
    # Extract results
    validation_issues = validation_result.get('issues', [])
    
    # Count invalid genes from issues
    gene_issues = [issue for issue in validation_issues if 'gene' in issue.get('message', '').lower()]
    invalid_gene_count = len(gene_issues)
    valid_genes = len(df.index) - invalid_gene_count
    
    print(f"\n✅ Gene Symbol Validation Complete!")
    print(f"   Valid genes: {valid_genes}/{len(df.index)} ({valid_genes/len(df.index)*100:.1f}%)")
    
    if gene_issues:
        print(f"   ❌ Invalid genes found: {len(gene_issues)}")
        print(f"   First 5 issues:")
        for issue in gene_issues[:5]:
            print(f"      - {issue.get('message', 'Unknown issue')}")
        issues.extend([f"❌ ERROR: {issue['message']}" for issue in gene_issues[:10]])
    
    # ========================================
    # STEP 4: COMPILE FINAL REPORT
    # ========================================
    print(f"\n{'='*70}")
    print(f"✅ VALIDATION COMPLETE")
    print(f"{'='*70}")
    
    # Determine overall decision
    error_count = sum(1 for i in issues if 'ERROR' in i)
    warning_count = sum(1 for i in issues if 'WARNING' in i)
    
    if error_count > 0:
        decision = "rejected"
        status_emoji = "❌"
    elif warning_count > 5:
        decision = "conditional_accept"
        status_emoji = "⚠️"
    else:
        decision = "accepted"
        status_emoji = "✅"
    
    print(f"\n📊 FINAL DECISION: {status_emoji} {decision.upper()}")
    print(f"   Total issues: {len(issues)}")
    print(f"   Errors: {error_count}")
    print(f"   Warnings: {warning_count}")
    
    if issues:
        print(f"\n📋 ISSUES FOUND (showing first 10):")
        for issue in issues[:10]:
            print(f"   {issue}")
        if len(issues) > 10:
            print(f"   ... and {len(issues)-10} more")
    else:
        print(f"\n🎉 No issues found - data quality is excellent!")
    
    print(f"\n📈 DATASET SUMMARY:")
    print(f"   Total genes: {len(df.index)}")
    print(f"   Valid genes: {valid_genes} ({valid_genes/len(df.index)*100:.1f}%)")
    print(f"   Cell lines: {len(df.columns)}")
    print(f"   Missing values: {missing_pct:.2f}%")
    
    # ========================================
    # STEP 5: SAVE DETAILED REPORT
    # ========================================
    print("\n📄 Saving validation report...")
    
    output_dir = Path("validation_output/depmap_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create detailed summary
    summary_path = output_dir / "validation_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("DEPMAP ACHILLES CRISPR VALIDATION REPORT\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Dataset: {csv_path}\n")
        f.write(f"Validation Date: {pd.Timestamp.now().isoformat()}\n\n")
        
        f.write("DATASET INFO:\n")
        f.write(f"  Total genes: {len(df.index)}\n")
        f.write(f"  Cell lines: {len(df.columns)}\n")
        f.write(f"  Missing values: {missing_pct:.2f}%\n")
        
        try:
            f.write(f"  Effect score range: {data_min:.3f} to {data_max:.3f}\n")
            if median_effect is not None:
                f.write(f"  Median effect: {median_effect:.3f}\n")
        except:
            pass
        
        f.write(f"\nGENE VALIDATION:\n")
        f.write(f"  Valid genes: {valid_genes}/{len(df.index)} ({valid_genes/len(df.index)*100:.1f}%)\n")
        f.write(f"  Invalid/suspicious genes: {invalid_gene_count}\n")
        
        f.write(f"\nVALIDATION DECISION: {decision.upper()}\n")
        f.write(f"  Errors: {error_count}\n")
        f.write(f"  Warnings: {warning_count}\n\n")
        
        if issues:
            f.write("ISSUES FOUND:\n")
            for issue in issues:
                f.write(f"  {issue}\n")
        else:
            f.write("No issues found!\n")
    
    print(f"✅ Summary saved: {summary_path}")
    
    # Save validation issues to CSV
    if validation_issues:
        issues_df = pd.DataFrame(validation_issues)
        issues_path = output_dir / "validation_issues.csv"
        issues_df.to_csv(issues_path, index=False)
        print(f"✅ Validation issues saved: {issues_path}")
    
    return {
        'decision': decision,
        'total_genes': len(df.index),
        'valid_genes': valid_genes,
        'invalid_genes': invalid_gene_count,
        'error_count': error_count,
        'warning_count': warning_count,
        'issues': issues,
        'missing_pct': missing_pct
    }


if __name__ == "__main__":
    print("="*70)
    print("DEPMAP ACHILLES CRISPR GENE EFFECT VALIDATION")
    print("="*70)
    print("\nCustom validator for DepMap data")
    print("This script performs:")
    print("  ✅ Gene symbol validation (NCBI/Ensembl)")
    print("  ✅ Data quality checks")
    print("  ✅ Statistical distribution analysis")
    print("  ✅ DepMap-specific formatting checks")
    print("\n")
    
    result = asyncio.run(validate_depmap_crispr_data())
    
    print(f"\n{'='*70}")
    print(f"VALIDATION {result['decision'].upper()}")
    print(f"{'='*70}")
    print(f"\n✅ Done! Check validation_output/depmap_reports/ for detailed results.")
