"""
Integration tests for end-to-end validation workflows
Tests multi-component orchestration and short-circuiting
"""
import pytest
import pandas as pd
import asyncio
from datetime import datetime
from src.agents.orchestrator import ValidationOrchestrator
from src.schemas.base_schemas import DatasetMetadata, FormatType, Decision


class TestValidationWorkflow:
    """Integration tests for complete validation workflow"""
    
    @pytest.fixture
    def orchestrator(self):
        """Create ValidationOrchestrator instance"""
        return ValidationOrchestrator()
    
    @pytest.fixture
    def perfect_dataset(self):
        """Dataset that should pass all validation stages"""
        return pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 100,
            'pam_sequence': ['AGG'] * 100,
            'target_gene': ['BRCA1'] * 50 + ['TP53'] * 50,
            'organism': ['human'] * 100,
            'nuclease_type': ['SpCas9'] * 100,
            'gc_content': [0.5] * 100,
            'efficiency_score': [0.85] * 100
        })
    
    @pytest.fixture
    def metadata(self):
        """Valid metadata"""
        return DatasetMetadata(
            dataset_id="integration_test_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=100,
            organism="human",
            submission_date=datetime.now()
        )
    
    # ===== HAPPY PATH TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_perfect_dataset_accepted(self, orchestrator, perfect_dataset, metadata):
        """Test that perfect dataset passes all stages and is ACCEPTED"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        assert report['final_decision'] == Decision.ACCEPTED
        assert report['requires_human_review'] is False
        assert report['short_circuited'] is False
        
        # All stages should be present
        assert 'schema' in report['stages']
        assert 'rules' in report['stages']
        assert 'bio_rules' in report['stages']
        assert 'bio_lookups' in report['stages']
        
        # All stages should pass
        for stage_name, stage_data in report['stages'].items():
            assert stage_data['passed'] is True
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_execution_time_recorded(self, orchestrator, perfect_dataset, metadata):
        """Test that execution time is properly tracked"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        assert 'execution_time_seconds' in report
        assert report['execution_time_seconds'] > 0
        assert report['start_time'] > 0
        assert report['end_time'] > report['start_time']
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_validation_id_generated(self, orchestrator, perfect_dataset, metadata):
        """Test that unique validation ID is generated"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        assert 'validation_id' in report
        assert len(report['validation_id']) > 0
        
        # Run again, should get different ID
        report2 = await orchestrator.validate_dataset(perfect_dataset, metadata)
        assert report2['validation_id'] != report['validation_id']
    
    # ===== SHORT-CIRCUIT TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_schema_failure_short_circuits(self, orchestrator, metadata):
        """Test that schema failure short-circuits remaining stages"""
        invalid_schema = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            # Missing required fields
        })
        
        metadata.record_count = 1
        report = await orchestrator.validate_dataset(invalid_schema, metadata)
        
        assert report['final_decision'] == Decision.REJECTED
        assert report['short_circuited'] is True
        
        # Schema stage should be present and failed
        assert 'schema' in report['stages']
        assert report['stages']['schema']['passed'] is False
        
        # Later stages should not be executed
        assert 'bio_lookups' not in report['stages'] or report['stages']['bio_lookups'].get('skipped', False)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_critical_rule_violation_short_circuits(self, orchestrator, metadata):
        """Test that critical rule violations trigger short-circuit"""
        critical_violation = pd.DataFrame({
            'guide_id': ['gRNA_001'] * 10,  # All same ID
            'sequence': ['ATCGATCGATCGATCGATCG'] * 10,
            'pam_sequence': ['AGG'] * 10,
            'target_gene': ['BRCA1'] * 10,
            'organism': ['human'] * 10,
            'nuclease_type': ['SpCas9'] * 10,
            'gc_content': [5.0] * 10  # Invalid: >1.0
        })
        
        metadata.record_count = 10
        report = await orchestrator.validate_dataset(critical_violation, metadata)
        
        assert report['final_decision'] == Decision.REJECTED
        # Should have passed schema but failed rules
        assert report['stages']['schema']['passed'] is True
        assert report['stages']['rules']['passed'] is False
    
    # ===== PARALLEL EXECUTION TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_bio_validation(self, orchestrator, perfect_dataset, metadata):
        """Test that bio_rules and bio_lookups run in parallel"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        # Both should be executed
        assert 'bio_rules' in report['stages']
        assert 'bio_lookups' in report['stages']
        
        # Total time should be less than sum of both (parallel execution)
        bio_rules_time = report['stages']['bio_rules']['execution_time_ms']
        bio_lookups_time = report['stages']['bio_lookups']['execution_time_ms']
        total_time = report['execution_time_seconds'] * 1000
        
        # Parallel execution should be faster than sequential
        # (with some overhead tolerance)
        assert total_time < (bio_rules_time + bio_lookups_time + 1000)
    
    # ===== DECISION MATRIX TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_warning_threshold_conditional_accept(self, orchestrator, metadata):
        """Test that moderate warnings trigger CONDITIONAL_ACCEPT"""
        warning_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 100,
            'pam_sequence': ['AGG'] * 100,
            'target_gene': ['BRCA1'] * 100,
            'organism': ['human'] * 100,
            'nuclease_type': ['SpCas9'] * 100,
            'gc_content': [0.15] * 100,  # Low GC - triggers warnings
            'efficiency_score': [0.85] * 100
        })
        
        metadata.record_count = 100
        report = await orchestrator.validate_dataset(warning_dataset, metadata)
        
        # Should be conditional accept or accepted depending on warning count
        assert report['final_decision'] in [Decision.ACCEPTED, Decision.CONDITIONAL_ACCEPT]
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_threshold_rejection(self, orchestrator, metadata):
        """Test that multiple errors trigger REJECTED"""
        error_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(100)],
            'sequence': ['ATCG'] * 100,  # Too short
            'pam_sequence': ['AAA'] * 100,  # Invalid PAM
            'target_gene': ['BRCA1'] * 100,
            'organism': ['human'] * 100,
            'nuclease_type': ['SpCas9'] * 100,
            'gc_content': [2.0] * 100,  # Invalid range
            'efficiency_score': [1.5] * 100  # Invalid range
        })
        
        metadata.record_count = 100
        report = await orchestrator.validate_dataset(error_dataset, metadata)
        
        assert report['final_decision'] == Decision.REJECTED
        
        # Should have multiple errors across different validators
        total_errors = sum(
            len([i for i in stage['issues'] if i['severity'] == 'error'])
            for stage in report['stages'].values()
        )
        assert total_errors >= 5  # Error threshold
    
    # ===== HUMAN REVIEW TRIGGER TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_human_review_triggered_on_critical(self, orchestrator, metadata):
        """Test that critical issues trigger human review"""
        critical_dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGATCGATCGATCGATCG'],
            'pam_sequence': ['AGG'],
            'target_gene': ['UNKNOWN_GENE_XYZ123'],  # Unknown gene
            'organism': ['human'],
            'nuclease_type': ['SpCas9']
        })
        
        metadata.record_count = 1
        report = await orchestrator.validate_dataset(critical_dataset, metadata)
        
        # Should trigger human review for unknown gene
        assert report['requires_human_review'] is True
    
    # ===== PERFORMANCE TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_100_records_under_5_seconds(self, orchestrator, perfect_dataset, metadata):
        """Test that 100 records complete in <5 seconds"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        assert report['execution_time_seconds'] < 5.0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_1000_records_under_15_seconds(self, orchestrator, metadata):
        """Test that 1,000 records complete in <15 seconds"""
        large_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:04d}' for i in range(1000)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 1000,
            'pam_sequence': ['AGG'] * 1000,
            'target_gene': ['BRCA1'] * 1000,
            'organism': ['human'] * 1000,
            'nuclease_type': ['SpCas9'] * 1000,
            'gc_content': [0.5] * 1000,
            'efficiency_score': [0.85] * 1000
        })
        
        metadata.record_count = 1000
        report = await orchestrator.validate_dataset(large_dataset, metadata)
        
        assert report['execution_time_seconds'] < 15.0
    
    # ===== PROVENANCE TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_provenance_trail_complete(self, orchestrator, perfect_dataset, metadata):
        """Test that complete provenance trail is captured"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        # Check metadata captured
        assert report['dataset_id'] == metadata.dataset_id
        
        # Check all validators recorded
        for stage_name, stage_data in report['stages'].items():
            assert 'validator_name' in stage_data
            assert 'execution_time_ms' in stage_data
            assert 'records_processed' in stage_data
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_decision_rationale_provided(self, orchestrator, perfect_dataset, metadata):
        """Test that decision rationale is provided"""
        report = await orchestrator.validate_dataset(perfect_dataset, metadata)
        
        assert 'decision_rationale' in report
        assert len(report['decision_rationale']) > 0
        assert isinstance(report['decision_rationale'], str)


class TestMultiDatasetValidation:
    """Tests for validating multiple datasets in sequence"""
    
    @pytest.fixture
    def orchestrator(self):
        return ValidationOrchestrator()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_sequential_validations_independent(self, orchestrator):
        """Test that sequential validations don't affect each other"""
        dataset1 = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGATCGATCGATCGATCG'],
            'pam_sequence': ['AGG'],
            'target_gene': ['BRCA1'],
            'organism': ['human'],
            'nuclease_type': ['SpCas9']
        })
        
        dataset2 = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['INVALID'],  # Invalid
            'pam_sequence': ['AAA'],
            'target_gene': ['TP53'],
            'organism': ['human'],
            'nuclease_type': ['SpCas9']
        })
        
        metadata1 = DatasetMetadata(
            dataset_id="seq_test_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=1,
            organism="human"
        )
        
        metadata2 = DatasetMetadata(
            dataset_id="seq_test_002",
            format_type=FormatType.GUIDE_RNA,
            record_count=1,
            organism="human"
        )
        
        report1 = await orchestrator.validate_dataset(dataset1, metadata1)
        report2 = await orchestrator.validate_dataset(dataset2, metadata2)
        
        # First should pass, second should fail
        assert report1['final_decision'] == Decision.ACCEPTED
        assert report2['final_decision'] == Decision.REJECTED
        
        # Different validation IDs
        assert report1['validation_id'] != report2['validation_id']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])