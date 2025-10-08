#!/usr/bin/env python3
"""
Validator Diagnostics - Test Detection Logic
Run from project root: python test_validator_diagnostics.py

Tests specific validator detection issues to debug test failures.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.validators.bio_rules import BioRulesValidator
from src.validators.rule_validator import RuleValidator


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_test(name: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}Testing: {name}{Colors.END}")
    print("=" * 60)


def print_result(expected: int, found: int, issues: list):
    if found >= expected:
        print(f"{Colors.GREEN}✓ PASS{Colors.END} - Expected {expected}+, found {found}")
    else:
        print(f"{Colors.RED}✗ FAIL{Colors.END} - Expected {expected}+, found {found}")
    
    for issue in issues:
        severity = issue.severity.value if hasattr(issue.severity, 'value') else issue.severity
        print(f"  [{severity}] {issue.message}")


def test_duplicate_sequences():
    """Test duplicate sequence detection"""
    print_test("Duplicate Sequences")
    
    # Create test data with duplicates
    df = pd.DataFrame([
        {"guide_id": "g1", "sequence": "ATCGATCGATCGATCGATCG"},
        {"guide_id": "g2", "sequence": "ATCGATCGATCGATCGATCG"},  # DUPLICATE
        {"guide_id": "g3", "sequence": "GCTAGCTAGCTAGCTAGCTA"},
    ])
    
    config = {
        'rules': {
            'duplicates': {
                'check_duplicate_rows': True,
                'unique_columns': [],
                'sequence_columns': ['sequence']  # KEY: Must specify sequence column
            },
            'bias': {},
            'consistency': {},
            'custom': []
        }
    }
    
    validator = RuleValidator(config=config)
    result = validator.validate(df)
    
    duplicate_issues = [i for i in result.issues if 'duplicate' in i.message.lower() and 'sequence' in i.field.lower()]
    print_result(1, len(duplicate_issues), duplicate_issues)
    
    return len(duplicate_issues) >= 1


def test_poly_t_stretch():
    """Test poly-T stretch detection"""
    print_test("Poly-T Stretch Detection")
    
    df = pd.DataFrame([
        {"guide_id": "g1", "sequence": "ATTTTTCGATCGATCGATCG"},  # Has TTTT
        {"guide_id": "g2", "sequence": "GCTAGCTAGCTAGCTAGCTA"},
        {"guide_id": "g3", "sequence": "atttttcgatcgatcgatcg"},  # Lowercase TTTT
    ])
    
    validator = BioRulesValidator()
    result = validator.validate(df, "guide_rna")
    
    polyt_issues = [i for i in result.issues if 'poly-t' in i.message.lower() or 'tttt' in i.message.lower()]
    print_result(1, len(polyt_issues), polyt_issues)
    
    return len(polyt_issues) >= 1


def test_guide_too_long():
    """Test guide length detection (>30bp)"""
    print_test("Guide Too Long Detection")
    
    df = pd.DataFrame([
        {"guide_id": "g1", "sequence": "ATCGATCGATCGATCGATCGATCGATCGATCG"},  # 32bp
        {"guide_id": "g2", "sequence": "GCTAGCTAGCTAGCTAGCTA"},  # 20bp OK
        {"guide_id": "g3", "sequence": "A" * 35},  # 35bp
    ])
    
    validator = BioRulesValidator()
    result = validator.validate(df, "guide_rna")
    
    length_issues = [i for i in result.issues if 'long' in i.message.lower() and ('30' in i.message or '>30' in i.message)]
    print_result(1, len(length_issues), length_issues)
    
    return len(length_issues) >= 1


def test_class_imbalance():
    """Test class imbalance detection"""
    print_test("Class Imbalance Detection")
    
    # Create data with 90/10 split (should trigger at 30% threshold)
    df = pd.DataFrame([
        {"guide_id": f"g{i}", "class": "high", "score": 0.9}
        for i in range(9)
    ] + [
        {"guide_id": "g9", "class": "low", "score": 0.2}  # Only 10%
    ])
    
    config = {
        'rules': {
            'duplicates': {},
            'bias': {
                'target_column': 'class',  # Use categorical column
                'imbalance_threshold': 0.3,  # Trigger if minority <30%
                'missing_value_threshold': 0.1
            },
            'consistency': {},
            'custom': []
        }
    }
    
    validator = RuleValidator(config=config)
    result = validator.validate(df)
    
    imbalance_issues = [i for i in result.issues if 'imbalance' in i.message.lower()]
    print_result(1, len(imbalance_issues), imbalance_issues)
    
    if imbalance_issues:
        for issue in imbalance_issues:
            print(f"\n  Metadata: {issue.metadata}")
    
    return len(imbalance_issues) >= 1


def test_missing_value_bias():
    """Test missing value bias detection"""
    print_test("Missing Value Bias Detection")
    
    # Create data with 40% missing in 'optional' column
    df = pd.DataFrame([
        {"guide_id": "g1", "score": 0.9, "optional": 1.0},
        {"guide_id": "g2", "score": 0.8, "optional": None},  # Missing
        {"guide_id": "g3", "score": 0.7, "optional": None},  # Missing
        {"guide_id": "g4", "score": 0.6, "optional": 2.0},
        {"guide_id": "g5", "score": 0.5, "optional": 3.0},
    ])
    
    config = {
        'rules': {
            'duplicates': {},
            'bias': {
                'target_column': 'score',
                'imbalance_threshold': 0.3,
                'missing_value_threshold': 0.1  # Trigger if >10% missing
            },
            'consistency': {},
            'custom': []
        }
    }
    
    validator = RuleValidator(config=config)
    result = validator.validate(df)
    
    missing_issues = [i for i in result.issues if 'missing' in i.message.lower()]
    print_result(1, len(missing_issues), missing_issues)
    
    return len(missing_issues) >= 1


def test_continuous_imbalance():
    """Test continuous data imbalance detection (NEW)"""
    print_test("Continuous Data Imbalance Detection")
    
    # Create skewed continuous data
    df = pd.DataFrame([
        {"guide_id": f"g{i}", "efficiency_score": 0.9 + (i * 0.01)}
        for i in range(25)
    ] + [
        {"guide_id": f"g{i}", "efficiency_score": 0.1}
        for i in range(25, 30)
    ])
    
    config = {
        'rules': {
            'duplicates': {},
            'bias': {
                'target_column': 'efficiency_score',  # Continuous column
                'imbalance_threshold': 0.3,
                'missing_value_threshold': 0.1
            },
            'consistency': {},
            'custom': []
        }
    }
    
    validator = RuleValidator(config=config)
    result = validator.validate(df)
    
    imbalance_issues = [i for i in result.issues if 'imbalance' in i.message.lower() or 'distribution' in i.message.lower()]
    print_result(1, len(imbalance_issues), imbalance_issues)
    
    return len(imbalance_issues) >= 1


def main():
    """Run all diagnostic tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'VALIDATOR DIAGNOSTICS':^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    
    tests = [
        ("Duplicate Sequences", test_duplicate_sequences),
        ("Poly-T Stretch", test_poly_t_stretch),
        ("Guide Too Long", test_guide_too_long),
        ("Class Imbalance", test_class_imbalance),
        ("Missing Value Bias", test_missing_value_bias),
        ("Continuous Imbalance", test_continuous_imbalance),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n{Colors.RED}✗ ERROR: {str(e)}{Colors.END}")
            results.append((name, False))
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if result else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"  {status} - {name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL VALIDATORS WORKING CORRECTLY! 🎉{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME VALIDATORS NEED FIXES{Colors.END}\n")
        print(f"{Colors.YELLOW}Next steps:{Colors.END}")
        print(f"  1. Check test data - does it actually have the expected issues?")
        print(f"  2. Check config - are you passing the right configuration?")
        print(f"  3. Check assertions - are tests checking correctly?\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
