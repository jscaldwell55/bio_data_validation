"""
Unit tests for Schema Validator
Tests foundational schema validation using Pydantic models
"""
import pytest
import pandas as pd
from datetime import datetime
from src.validators.schema_validator import SchemaValidator
from src.schemas.base_schemas import (
    DatasetMetadata,
    ValidationResult,
    ValidationSeverity,
    FormatType
)


class TestSchemaValidator:
    """Test suite for SchemaValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create SchemaValidator instance"""
        return SchemaValidator()
    
    @pytest.fixture
    def valid_guide_rna_data(self):
        """Valid guide RNA dataset"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'TTAATTAATTAATTAATTAA'],
            'pam_sequence': ['AGG', 'TGG', 'CGG'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human', 'human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9'],
            'gc_content': [0.5, 0.5, 0.0],
            'efficiency_score': [0.85, 0.92, 0.78]
        })
    
    @pytest.fixture
    def invalid_missing_fields_data(self):
        """Data missing required fields"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA']
            # Missing: pam_sequence, target_gene, organism, nuclease_type
        })
    
    @pytest.fixture
    def invalid_type_data(self):
        """Data with type violations"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['BRCA1', 'TP53'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9'],
            'gc_content': ['invalid', 0.5],  # First value is string, should be float
            'efficiency_score': [0.85, 1.5]  # Second value exceeds valid range
        })
    
    @pytest.fixture
    def valid_metadata(self):
        """Valid dataset metadata"""
        return DatasetMetadata(
            dataset_id="experiment_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=3,
            organism="human",
            submission_date=datetime.now()
        )
    
    # Test: Valid data passes validation
    def test_valid_data_passes(self, validator, valid_guide_rna_data, valid_metadata):
        """Test that valid data passes all schema checks"""
        result = validator.validate(valid_guide_rna_data, valid_metadata)
        
        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.validator_name == "SchemaValidator"
        assert len(result.issues) == 0
        assert result.severity == ValidationSeverity.INFO
    
    # Test: Missing required fields detected
    def test_missing_required_fields(self, validator, invalid_missing_fields_data, valid_metadata):
        """Test detection of missing required columns"""
        result = validator.validate(invalid_missing_fields_data, valid_metadata)

        assert result.passed is False
        assert result.severity == ValidationSeverity.ERROR
        assert len(result.issues) > 0

        # Check that missing fields are reported
        issue_messages = [issue.message for issue in result.issues]
        assert any('pam_sequence' in msg for msg in issue_messages)
        assert any('target_gene' in msg for msg in issue_messages)
    
    # Test: Type violations detected
    def test_type_violations(self, validator, invalid_type_data, valid_metadata):
        """Test detection of incorrect data types"""
        result = validator.validate(invalid_type_data, valid_metadata)
        
        assert result.passed is False
        assert len(result.issues) > 0
        
        # Check for type-related errors
        issue_messages = ' '.join([issue.message for issue in result.issues])
        assert 'type' in issue_messages.lower() or 'invalid' in issue_messages.lower()
    
    # Test: Empty dataset rejected
    def test_empty_dataset(self, validator, valid_metadata):
        """Test that empty datasets are rejected"""
        empty_df = pd.DataFrame()
        result = validator.validate(empty_df, valid_metadata)

        assert result.passed is False
        assert result.severity == ValidationSeverity.ERROR
    
    # Test: Invalid characters in sequence
    def test_invalid_sequence_characters(self, validator, valid_metadata):
        """Test detection of invalid DNA characters"""
        invalid_seq_data = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCG123XYZ'],  # Invalid characters
            'pam_sequence': ['AGG'],
            'target_gene': ['BRCA1'],
            'organism': ['human'],
            'nuclease_type': ['SpCas9'],
            'gc_content': [0.5],
            'efficiency_score': [0.85]
        })
        
        result = validator.validate(invalid_seq_data, valid_metadata)
        
        assert result.passed is False
        assert any('sequence' in issue.field.lower() for issue in result.issues)
    
    # Test: Execution time recorded
    def test_execution_time_recorded(self, validator, valid_guide_rna_data, valid_metadata):
        """Test that execution time is properly recorded"""
        result = validator.validate(valid_guide_rna_data, valid_metadata)
        
        assert result.execution_time_ms > 0
        assert isinstance(result.execution_time_ms, (int, float))
    
    # Test: Record count matches
    def test_record_count_matches(self, validator, valid_guide_rna_data, valid_metadata):
        """Test that records_processed matches actual data"""
        result = validator.validate(valid_guide_rna_data, valid_metadata)
        
        assert result.records_processed == len(valid_guide_rna_data)
        assert result.records_processed == valid_metadata.record_count
    
    # Test: Different format types
    @pytest.mark.parametrize("format_type", [
        FormatType.GUIDE_RNA,
        FormatType.FASTA,
        FormatType.GENBANK,
        FormatType.FASTQ
    ])
    def test_different_format_types(self, validator, valid_guide_rna_data, format_type):
        """Test validation with different format types"""
        metadata = DatasetMetadata(
            dataset_id="test_001",
            format_type=format_type,
            record_count=len(valid_guide_rna_data),
            organism="human"
        )
        
        result = validator.validate(valid_guide_rna_data, metadata)
        assert isinstance(result, ValidationResult)
    
    # Test: Null values detected
    def test_null_values_detected(self, validator, valid_metadata):
        """Test detection of null/missing values"""
        data_with_nulls = pd.DataFrame({
            'guide_id': ['gRNA_001', None, 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', None],
            'pam_sequence': ['AGG', 'TGG', 'CGG'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human', 'human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9']
        })
        
        result = validator.validate(data_with_nulls, valid_metadata)
        
        assert result.passed is False
        assert any('null' in issue.message.lower() or 'missing' in issue.message.lower() 
                  for issue in result.issues)


class TestSchemaValidatorEdgeCases:
    """Edge case tests for SchemaValidator"""
    
    @pytest.fixture
    def validator(self):
        return SchemaValidator()
    
    def test_single_record_dataset(self, validator):
        """Test validation of single-record dataset"""
        single_record = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGATCGATCGATCGATCG'],
            'pam_sequence': ['AGG'],
            'target_gene': ['BRCA1'],
            'organism': ['human'],
            'nuclease_type': ['SpCas9']
        })
        
        metadata = DatasetMetadata(
            dataset_id="single_test",
            format_type=FormatType.GUIDE_RNA,
            record_count=1,
            organism="human"
        )
        
        result = validator.validate(single_record, metadata)
        assert isinstance(result, ValidationResult)
        assert result.records_processed == 1
    
    def test_large_dataset_performance(self, validator):
        """Test performance with large dataset (10,000 records)"""
        import numpy as np
        
        # Generate 10,000 records
        n_records = 10000
        large_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:05d}' for i in range(n_records)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * n_records,
            'pam_sequence': ['AGG'] * n_records,
            'target_gene': ['BRCA1'] * n_records,
            'organism': ['human'] * n_records,
            'nuclease_type': ['SpCas9'] * n_records,
            'gc_content': np.random.uniform(0.3, 0.7, n_records),
            'efficiency_score': np.random.uniform(0.5, 1.0, n_records)
        })
        
        metadata = DatasetMetadata(
            dataset_id="large_test",
            format_type=FormatType.GUIDE_RNA,
            record_count=n_records,
            organism="human"
        )
        
        result = validator.validate(large_dataset, metadata)
        
        # Should complete in <5 seconds for 10K records
        assert result.execution_time_ms < 5000
        assert result.records_processed == n_records
    
    def test_unicode_characters_in_fields(self, validator):
        """Test handling of unicode characters"""
        unicode_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['BRCA1', 'TP53'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9'],
            'notes': ['Test note', 'Unicode: 日本語 🧬']  # Optional field with unicode
        })
        
        metadata = DatasetMetadata(
            dataset_id="unicode_test",
            format_type=FormatType.GUIDE_RNA,
            record_count=2,
            organism="human"
        )
        
        result = validator.validate(unicode_data, metadata)
        # Should handle unicode gracefully
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])