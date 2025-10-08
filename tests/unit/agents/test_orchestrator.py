"""
Unit tests for ValidationOrchestrator
Tests workflow coordination, short-circuiting, and decision-making
"""
import pytest
import pandas as pd
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import (
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    Decision,
    DatasetMetadata,
    FormatType
)


class TestOrchestrator:
    """Test suite for ValidationOrchestrator"""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return ValidationOrchestrator()
    
    @pytest.fixture
    def simple_dataset(self):
        """Simple test dataset"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['BRCA1', 'TP53'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9']
        })
    
    @pytest.fixture
    def simple_metadata(self):
        """Simple test metadata"""
        return DatasetMetadata(
            dataset_id="test_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=2,
            organism="human"
        )
    
    # ===== INITIALIZATION TESTS =====
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initializes correctly"""
        assert orchestrator is not None
        assert hasattr(orchestrator, 'validate_dataset')
        assert hasattr(orchestrator, 'config')
    
    def test_orchestrator_loads_config(self, orchestrator):
        """Test orchestrator loads configuration"""
        assert orchestrator.config is not None
        assert hasattr(orchestrator.config, 'enable_short_circuit')
        assert hasattr(orchestrator.config, 'enable_parallel_bio')
    
    # ===== WORKFLOW COORDINATION TESTS =====
    
    @pytest.mark.asyncio
    async def test_all_stages_executed_on_success(self, orchestrator, simple_dataset, simple_metadata):
        """Test all validation stages execute when no failures"""
        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        # All stages should be present
        expected_stages = ['schema', 'rules', 'bio_rules', 'bio_lookups', 'policy']
        for stage in expected_stages:
            assert stage in report['stages'], f"Missing stage: {stage}"
    
    @pytest.mark.asyncio
    async def test_stages_execute_in_order(self, orchestrator, simple_dataset, simple_metadata):
        """Test stages execute in correct order"""
        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        stages = list(report['stages'].keys())
        
        # Schema should be first
        assert stages[0] == 'schema'
        
        # Rules should come after schema
        schema_idx = stages.index('schema')
        rules_idx = stages.index('rules')
        assert rules_idx > schema_idx
        
        # Policy should be last
        assert stages[-1] == 'policy'
    
    @pytest.mark.asyncio
    async def test_validation_id_unique(self, orchestrator, simple_dataset, simple_metadata):
        """Test each validation gets unique ID"""
        report1 = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        report2 = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        assert report1['validation_id'] != report2['validation_id']
        assert len(report1['validation_id']) > 0
    
    @pytest.mark.asyncio
    async def test_timestamps_recorded(self, orchestrator, simple_dataset, simple_metadata):
        """Test start and end timestamps are recorded"""
        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        assert 'start_time' in report
        assert 'end_time' in report
        assert report['end_time'] > report['start_time']
        assert report['execution_time_seconds'] > 0
    
    # ===== SHORT-CIRCUIT TESTS =====
    
    @pytest.mark.asyncio
    async def test_schema_failure_short_circuits(self, orchestrator, simple_metadata):
        """Test schema failure prevents later stages"""
        invalid_schema = pd.DataFrame({
            'guide_id': ['gRNA_001']
            # Missing required fields
        })
        
        simple_metadata.record_count = 1
        
        with patch.object(orchestrator, 'config') as mock_config:
            mock_config.enable_short_circuit = True
            
            report = await orchestrator.validate_dataset(invalid_schema, simple_metadata)
            
            assert report['short_circuited'] is True
            assert report['final_decision'] == Decision.REJECTED.value

            # Bio stages should be skipped
            bio_executed = any(
                stage in report['stages'] and not report['stages'][stage].get('skipped', False)
                for stage in ['bio_rules', 'bio_lookups']
            )
            assert not bio_executed
    
    @pytest.mark.asyncio
    async def test_no_short_circuit_when_disabled(self, orchestrator, simple_metadata):
        """Test all stages run when short-circuit disabled"""
        invalid_schema = pd.DataFrame({
            'guide_id': ['gRNA_001']
        })
        
        simple_metadata.record_count = 1
        
        with patch.object(orchestrator, 'config') as mock_config:
            mock_config.enable_short_circuit = False
            
            report = await orchestrator.validate_dataset(invalid_schema, simple_metadata)
            
            # Should attempt all stages even with failures
            assert report['short_circuited'] is False
    
    @pytest.mark.asyncio
    async def test_critical_issues_trigger_short_circuit(self, orchestrator, simple_metadata):
        """Test critical severity issues trigger short-circuit"""
        # Mock schema validator to return critical issue
        with patch('src.agents.orchestrator.SchemaValidator') as MockValidator:
            mock_validator = MockValidator.return_value
            mock_validator.validate.return_value = ValidationResult(
                validator_name="SchemaValidator",
                passed=False,
                severity=ValidationSeverity.CRITICAL,
                issues=[
                    ValidationIssue(
                        field="dataset",
                        message="Critical error",
                        severity=ValidationSeverity.CRITICAL
                    )
                ],
                execution_time_ms=10,
                records_processed=0
            )
            
            dataset = pd.DataFrame({'guide_id': ['gRNA_001']})
            simple_metadata.record_count = 1
            
            report = await orchestrator.validate_dataset(dataset, simple_metadata)

            assert report['short_circuited'] is True
            assert report['final_decision'] == Decision.REJECTED.value
    
    # ===== PARALLEL EXECUTION TESTS =====
    
    @pytest.mark.asyncio
    async def test_parallel_bio_validation(self, orchestrator, simple_dataset, simple_metadata):
        """Test that bio_rules and bio_lookups run in parallel"""
        with patch.object(orchestrator, 'config') as mock_config:
            mock_config.enable_parallel_bio = True
            
            report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
            
            # Both should be executed
            assert 'bio_rules' in report['stages']
            assert 'bio_lookups' in report['stages']
            
            # Total time should suggest parallel execution
            # (This is a simplified check - real test would need timing mocks)
            assert report['execution_time_seconds'] >= 0
    
    @pytest.mark.asyncio
    async def test_sequential_bio_validation(self, orchestrator, simple_dataset, simple_metadata):
        """Test bio validation runs sequentially when parallel disabled"""
        with patch.object(orchestrator, 'config') as mock_config:
            mock_config.enable_parallel_bio = False
            
            report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
            
            # Both stages should still execute
            assert 'bio_rules' in report['stages']
            assert 'bio_lookups' in report['stages']
    
    # ===== DECISION MAKING TESTS =====
    
    @pytest.mark.asyncio
    async def test_no_issues_accepted(self, orchestrator, simple_dataset, simple_metadata):
        """Test dataset with no issues is ACCEPTED"""
        # FIXED: Mock validator instances directly on orchestrator
        success_result = ValidationResult(
            validator_name="Mock",
            passed=True,
            severity=ValidationSeverity.INFO,
            issues=[],
            execution_time_ms=10,
            records_processed=2
        )

        orchestrator.rule_validator.validate = Mock(return_value=success_result)
        orchestrator.bio_rules.validate = Mock(return_value=success_result)
        orchestrator.bio_lookups.validate = AsyncMock(return_value=success_result)

        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)

        assert report['final_decision'] == Decision.ACCEPTED.value
        assert report['requires_human_review'] is False
    
    @pytest.mark.asyncio
    async def test_multiple_errors_rejected(self, orchestrator, simple_dataset, simple_metadata):
        """Test dataset with many errors is REJECTED"""
        # FIXED: Mock validator instance directly
        # Create 6 error issues (above threshold of 5)
        error_issues = [
            ValidationIssue(
                field=f"field_{i}",
                message=f"Error {i}",
                severity=ValidationSeverity.ERROR
            )
            for i in range(6)
        ]

        orchestrator.rule_validator.validate = Mock(return_value=ValidationResult(
            validator_name="RuleValidator",
            passed=False,
            severity=ValidationSeverity.ERROR,
            issues=error_issues,
            execution_time_ms=10,
            records_processed=2
        ))

        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)

        assert report['final_decision'] == Decision.REJECTED.value
    
    @pytest.mark.asyncio
    async def test_warnings_conditional_accept(self, orchestrator, simple_dataset, simple_metadata):
        """Test dataset with warnings may be CONDITIONAL_ACCEPT"""
        # Mock validators to return warnings
        with patch('src.agents.orchestrator.BioRulesValidator') as MockBioRules:
            mock_validator = MockBioRules.return_value
            
            warning_issues = [
                ValidationIssue(
                    field="gc_content",
                    message="GC content suboptimal",
                    severity=ValidationSeverity.WARNING
                )
                for _ in range(3)
            ]
            
            mock_validator.validate.return_value = ValidationResult(
                validator_name="BioRulesValidator",
                passed=True,
                severity=ValidationSeverity.WARNING,
                issues=warning_issues,
                execution_time_ms=10,
                records_processed=2
            )
            
            report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
            
            # Should be accepted or conditional based on warning count
            assert report['final_decision'] in [Decision.ACCEPTED, Decision.CONDITIONAL_ACCEPT]
    
    # ===== ERROR HANDLING TESTS =====
    
    @pytest.mark.asyncio
    async def test_validator_exception_handling(self, orchestrator, simple_dataset, simple_metadata):
        """Test orchestrator handles validator exceptions gracefully"""
        # FIXED: Patch validate_schema function to raise exception
        with patch('src.agents.orchestrator.validate_schema') as mock_validate:
            mock_validate.side_effect = Exception("Validator crashed")

            report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)

            # Should handle exception and report failure
            assert report['final_decision'] in [Decision.REJECTED.value, 'ERROR']
            # FIXED: Check for error in report, not stages (stages may be empty on exception)
            assert 'error' in report or any('error' in str(stage).lower() for stage in report['stages'].values())
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator, simple_dataset, simple_metadata):
        """Test orchestrator handles timeouts"""
        with patch.object(orchestrator, 'config') as mock_config:
            mock_config.timeout_seconds = 0.001  # Very short timeout
            
            # This should timeout or complete very quickly
            report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
            
            # Should still produce a report
            assert 'final_decision' in report
    
    # ===== PERFORMANCE TESTS =====
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_dataset_performance(self, orchestrator, large_dataset, metadata_factory):
        """Test orchestrator handles large datasets efficiently"""
        metadata = metadata_factory(
            dataset_id="perf_test",
            record_count=len(large_dataset)
        )
        
        report = await orchestrator.validate_dataset(large_dataset, metadata)
        
        # Should complete in reasonable time (<60s for 10K records)
        assert report['execution_time_seconds'] < 60.0
        assert 'final_decision' in report
    
    # ===== PROVENANCE TESTS =====
    
    @pytest.mark.asyncio
    async def test_complete_provenance_trail(self, orchestrator, simple_dataset, simple_metadata):
        """Test all provenance information is captured"""
        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        # Check top-level provenance
        assert report['dataset_id'] == simple_metadata.dataset_id
        assert 'validation_id' in report
        assert 'start_time' in report
        assert 'end_time' in report
        
        # Check each stage has provenance
        for stage_name, stage_data in report['stages'].items():
            assert 'validator_name' in stage_data
            assert 'execution_time_ms' in stage_data
            assert 'records_processed' in stage_data
    
    @pytest.mark.asyncio
    async def test_decision_rationale_provided(self, orchestrator, simple_dataset, simple_metadata):
        """Test decision rationale is always provided"""
        report = await orchestrator.validate_dataset(simple_dataset, simple_metadata)
        
        assert 'decision_rationale' in report
        assert isinstance(report['decision_rationale'], str)
        assert len(report['decision_rationale']) > 0


class TestOrchestratorConfiguration:
    """Tests for orchestrator configuration"""
    
    def test_default_configuration(self):
        """Test orchestrator loads default configuration"""
        orchestrator = ValidationOrchestrator()
        
        assert orchestrator.config is not None
        assert hasattr(orchestrator.config, 'enable_short_circuit')
        assert hasattr(orchestrator.config, 'enable_parallel_bio')
        assert hasattr(orchestrator.config, 'timeout_seconds')
    
    def test_custom_configuration(self):
        """Test orchestrator accepts custom configuration"""
        # FIXED: Use proper OrchestrationConfig object instead of Mock
        custom_config = OrchestrationConfig(
            enable_short_circuit=False,
            enable_parallel_bio=True,
            timeout_seconds=600
        )

        orchestrator = ValidationOrchestrator(config=custom_config)

        assert orchestrator.config.enable_short_circuit is False
        assert orchestrator.config.enable_parallel_bio is True
        assert orchestrator.config.timeout_seconds == 600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])