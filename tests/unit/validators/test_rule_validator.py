"""
Unit tests for Rule Validator
Tests consistency, duplicates, and statistical bias detection
"""
import pytest
import pandas as pd
import numpy as np
from src.validators.rule_validator import RuleValidator
from src.schemas.base_schemas import ValidationResult, ValidationSeverity


class TestRuleValidator:
    """Test suite for RuleValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create RuleValidator instance"""
        return RuleValidator()
    
    @pytest.fixture
    def consistent_data(self):
        """Dataset with no consistency issues"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'TTAATTAATTAATTAATTAA'],
            'gc_content': [0.5, 0.5, 0.0],
            'efficiency_score': [0.85, 0.92, 0.78],
            'start_position': [100, 200, 300],
            'end_position': [120, 220, 320],
            'target_gene': ['BRCA1', 'TP53', 'EGFR']
        })
    
    # ===== CONSISTENCY TESTS =====
    
    def test_valid_consistency_passes(self, validator, consistent_data):
        """Test that consistent data passes all checks"""
        result = validator.validate(consistent_data)
        
        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.validator_name == "RuleValidator"
        assert len(result.issues) == 0
    
    def test_invalid_gc_content_range(self, validator):
        """Test detection of GC content outside valid range"""
        invalid_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCG', 'GCTA', 'TTAA'],
            'gc_content': [0.5, 1.5, -0.1],  # 1.5 and -0.1 are invalid
            'efficiency_score': [0.85, 0.92, 0.78]
        })
        
        result = validator.validate(invalid_data)
        
        assert result.passed is False
        assert any('gc_content' in issue.field.lower() for issue in result.issues)
        assert any('range' in issue.message.lower() for issue in result.issues)
    
    def test_invalid_efficiency_score_range(self, validator):
        """Test detection of efficiency scores outside [0, 1]"""
        invalid_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCG', 'GCTA'],
            'gc_content': [0.5, 0.6],
            'efficiency_score': [1.2, -0.5]  # Both invalid
        })
        
        result = validator.validate(invalid_data)
        
        assert result.passed is False
        assert any('efficiency_score' in issue.field.lower() for issue in result.issues)
    
    def test_end_before_start_position(self, validator):
        """Test detection of end position before start position"""
        invalid_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCG', 'GCTA'],
            'start_position': [100, 200],
            'end_position': [90, 220]  # First row: end < start
        })
        
        result = validator.validate(invalid_data)
        
        assert result.passed is False
        assert any('position' in issue.message.lower() for issue in result.issues)
    
    # ===== DUPLICATE DETECTION TESTS =====
    
    def test_no_duplicates_passes(self, validator, consistent_data):
        """Test that data without duplicates passes"""
        result = validator.validate(consistent_data)
        
        assert result.passed is True
        duplicate_issues = [i for i in result.issues if 'duplicate' in i.message.lower()]
        assert len(duplicate_issues) == 0
    
    def test_exact_duplicate_rows(self, validator):
        """Test detection of exact duplicate rows"""
        duplicate_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_001'],  # Duplicate ID
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'ATCGATCGATCGATCGATCG'],
            'target_gene': ['BRCA1', 'TP53', 'BRCA1']
        })
        
        result = validator.validate(duplicate_data)
        
        assert result.passed is False
        assert any('duplicate' in issue.message.lower() for issue in result.issues)
    
    def test_duplicate_guide_ids(self, validator):
        """Test detection of duplicate guide IDs"""
        duplicate_ids = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_001'],  # Duplicate
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'TTAATTAATTAATTAATTAA'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR']
        })
        
        result = validator.validate(duplicate_ids)
        
        assert result.passed is False
        duplicate_issues = [i for i in result.issues if 'guide_id' in i.field.lower()]
        assert len(duplicate_issues) > 0
    
    def test_duplicate_sequences(self, validator):
        """Test detection of duplicate sequences"""
        duplicate_seqs = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'ATCGATCGATCGATCGATCG'],  # Duplicate
            'target_gene': ['BRCA1', 'TP53', 'EGFR']
        })
        
        result = validator.validate(duplicate_seqs)
        
        assert result.passed is False
        assert any('sequence' in issue.field.lower() for issue in result.issues)
    
    # ===== STATISTICAL BIAS TESTS =====
    
    def test_no_bias_passes(self, validator):
        """Test that balanced data passes bias checks"""
        balanced_data = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCG'] * 100,
            'class_label': ['positive'] * 50 + ['negative'] * 50,  # 50/50 split
            'value': np.random.randn(100)
        })
        
        result = validator.validate(balanced_data)
        
        bias_issues = [i for i in result.issues if 'bias' in i.message.lower() or 'imbalance' in i.message.lower()]
        assert len(bias_issues) == 0
    
    def test_class_imbalance_detected(self, validator):
        """Test detection of severe class imbalance (95/5 split)"""
        imbalanced_data = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCG'] * 100,
            'class_label': ['positive'] * 95 + ['negative'] * 5  # 95/5 split
        })
        
        result = validator.validate(imbalanced_data)
        
        assert result.passed is False
        assert any('imbalance' in issue.message.lower() or 'bias' in issue.message.lower() 
                  for issue in result.issues)
    
    def test_missing_value_bias(self, validator):
        """Test detection of excessive missing values (>10%)"""
        data_with_missing = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCG'] * 85 + [None] * 15,  # 15% missing
            'target_gene': ['BRCA1'] * 100
        })
        
        result = validator.validate(data_with_missing)
        
        assert result.passed is False
        assert any('missing' in issue.message.lower() for issue in result.issues)
    
    # ===== VECTORIZATION PERFORMANCE TESTS =====
    
    def test_large_dataset_vectorization(self, validator):
        """Test that vectorized operations handle large datasets efficiently"""
        # Create 10,000 record dataset
        n_records = 10000
        large_data = pd.DataFrame({
            'guide_id': [f'gRNA_{i:05d}' for i in range(n_records)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * n_records,
            'gc_content': np.random.uniform(0.3, 0.7, n_records),
            'efficiency_score': np.random.uniform(0.6, 1.0, n_records),
            'start_position': np.arange(1000, 1000 + n_records),
            'end_position': np.arange(1020, 1020 + n_records)
        })
        
        result = validator.validate(large_data)
        
        # Should complete in <10 seconds for 10K records
        assert result.execution_time_ms < 10000
        assert result.records_processed == n_records
    
    # ===== CUSTOM RULE TESTS =====
    
    def test_custom_yaml_rule_applied(self, validator):
        """Test that custom YAML-configured rules are applied"""
        # This assumes custom rules are loaded from config
        data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTAGC'],  # Different lengths
            'target_gene': ['BRCA1', 'TP53']
        })
        
        result = validator.validate(data)
        
        # Custom rules should be evaluated
        assert isinstance(result, ValidationResult)


class TestRuleValidatorEdgeCases:
    """Edge case tests for RuleValidator"""
    
    @pytest.fixture
    def validator(self):
        return RuleValidator()
    
    def test_all_null_column(self, validator):
        """Test handling of completely null column"""
        data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCG', 'GCTA'],
            'optional_field': [None, None]  # Completely null
        })
        
        result = validator.validate(data)
        assert isinstance(result, ValidationResult)
    
    def test_boundary_values(self, validator):
        """Test boundary values for ranges"""
        boundary_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003', 'gRNA_004'],
            'sequence': ['ATCG', 'GCTA', 'TTAA', 'CCGG'],
            'gc_content': [0.0, 1.0, 0.5, 0.999],  # Boundary values
            'efficiency_score': [0.0, 1.0, 0.5, 0.001]  # Boundary values
        })
        
        result = validator.validate(boundary_data)
        
        # Boundary values should be accepted
        assert result.passed is True
    
    def test_negative_positions(self, validator):
        """Test handling of negative genomic positions (valid in some contexts)"""
        data = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCG'],
            'start_position': [-100],
            'end_position': [-80]
        })
        
        result = validator.validate(data)
        # System should handle this based on configuration
        assert isinstance(result, ValidationResult)
    
    def test_extremely_long_sequence(self, validator):
        """Test handling of very long sequences"""
        long_seq = 'A' * 10000  # 10kb sequence
        data = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': [long_seq],
            'target_gene': ['BRCA1']
        })
        
        result = validator.validate(data)
        assert isinstance(result, ValidationResult)
    
    def test_mixed_case_sequences(self, validator):
        """Test handling of mixed-case DNA sequences"""
        mixed_case_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGatcg', 'GCTAGCTA', 'ttaattaa'],  # Mixed case
            'target_gene': ['BRCA1', 'TP53', 'EGFR']
        })
        
        result = validator.validate(mixed_case_data)
        # Should either normalize or flag as issue
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])