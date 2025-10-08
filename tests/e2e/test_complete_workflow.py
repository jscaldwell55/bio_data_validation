"""
End-to-end tests for complete validation workflows
Tests entire system from data ingestion to final decision
"""
import pytest
import pandas as pd
import asyncio
from pathlib import Path
from datetime import datetime
from src.agents.orchestrator import ValidationOrchestrator
from src.schemas.base_schemas import DatasetMetadata, FormatType, Decision


class TestCompleteWorkflow:
    """End-to-end workflow tests"""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with full system"""
        return ValidationOrchestrator()
    
    @pytest.fixture
    def example_data_dir(self):
        """Path to example data directory"""
        return Path(__file__).parent.parent.parent / "data" / "examples"
    
    # ===== COMPLETE VALIDATION WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_perfect_dataset_end_to_end(self, orchestrator):
        """Test complete workflow with perfect dataset"""
        # Create perfect dataset
        dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(20)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 20,
            'pam_sequence': ['AGG'] * 20,
            'target_gene': ['BRCA1'] * 20,
            'organism': ['human'] * 20,
            'nuclease_type': ['SpCas9'] * 20,
            'gc_content': [0.5] * 20,
            'efficiency_score': [0.85] * 20
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_perfect_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=20,
            organism="human"
        )
        
        # Execute full validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Verify complete report structure
        assert 'validation_id' in report
        assert 'final_decision' in report
        assert 'stages' in report
        assert 'execution_time_seconds' in report
        
        # Verify all stages executed
        assert 'schema' in report['stages']
        assert 'rules' in report['stages']
        assert 'bio_rules' in report['stages']
        
        # Verify decision
        assert report['final_decision'] == Decision.ACCEPTED
        assert report['requires_human_review'] is False
        
        # Verify provenance
        assert report['dataset_id'] == "e2e_perfect_001"
        assert report['start_time'] > 0
        assert report['end_time'] > report['start_time']
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_flawed_dataset_end_to_end(self, orchestrator):
        """Test complete workflow with flawed dataset"""
        # Create dataset with multiple issues
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_001', 'gRNA_003'],  # Duplicate
            'sequence': ['ATCG', 'INVALID123', 'TTTTTTTTTTTTTTTTTTTT'],  # Too short, invalid, poly-T
            'pam_sequence': ['AAA', 'TGG', 'XYZ'],  # Invalid, valid, invalid
            'target_gene': ['', 'BRCA1', 'UNKNOWN_GENE'],  # Missing, valid, unknown
            'organism': ['human', 'human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9'],
            'gc_content': [1.5, 0.5, 0.0],  # Out of range, valid, low
            'efficiency_score': [1.2, 0.85, -0.1]  # Out of range, valid, negative
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_flawed_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=3,
            organism="human"
        )
        
        # Execute full validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Verify report
        assert report['final_decision'] == Decision.REJECTED
        
        # Verify issues detected across multiple stages
        total_issues = sum(
            len(stage['issues'])
            for stage in report['stages'].values()
            if 'issues' in stage
        )
        assert total_issues > 5  # Should detect multiple issues
        
        # Verify different issue types detected
        issue_fields = set()
        for stage in report['stages'].values():
            if 'issues' in stage:
                for issue in stage['issues']:
                    issue_fields.add(issue['field'])
        
        assert len(issue_fields) > 3  # Multiple fields flagged
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_conditional_accept_workflow(self, orchestrator):
        """Test workflow resulting in conditional accept"""
        # Create dataset with warnings but no errors
        dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(10)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 10,
            'pam_sequence': ['AGG'] * 10,
            'target_gene': ['BRCA1'] * 10,
            'organism': ['human'] * 10,
            'nuclease_type': ['SpCas9'] * 10,
            'gc_content': [0.25] * 10,  # Low GC content (warning)
            'efficiency_score': [0.6] * 10  # Low efficiency (warning)
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_conditional_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=10,
            organism="human"
        )
        
        # Execute validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Should be conditional accept
        assert report['final_decision'] in [Decision.CONDITIONAL_ACCEPT, Decision.ACCEPTED]
    
    # ===== FILE-BASED WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_csv_file_validation_workflow(self, orchestrator, example_data_dir, tmp_path):
        """Test complete workflow with CSV file input"""
        # Create CSV file
        csv_file = tmp_path / "test_guides.csv"
        data = """guide_id,sequence,pam_sequence,target_gene,organism,nuclease_type
gRNA_001,ATCGATCGATCGATCGATCG,AGG,BRCA1,human,SpCas9
gRNA_002,GCTAGCTAGCTAGCTAGCTA,TGG,TP53,human,SpCas9
gRNA_003,GATTACAGATTACAGATTAC,CGG,EGFR,human,SpCas9"""
        csv_file.write_text(data)
        
        # Load and validate
        df = pd.read_csv(csv_file)
        metadata = DatasetMetadata(
            dataset_id="e2e_csv_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=len(df),
            organism="human"
        )
        
        report = await orchestrator.validate_dataset(df, metadata)
        
        # Verify success
        assert report['final_decision'] == Decision.ACCEPTED
    
    # ===== LARGE DATASET WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.slow
    async def test_large_dataset_workflow(self, orchestrator):
        """Test workflow with large dataset (1000 records)"""
        import numpy as np
        
        # Create 1000 record dataset
        n_records = 1000
        dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:04d}' for i in range(n_records)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * n_records,
            'pam_sequence': np.random.choice(['AGG', 'TGG', 'CGG'], n_records),
            'target_gene': np.random.choice(['BRCA1', 'TP53', 'EGFR'], n_records),
            'organism': ['human'] * n_records,
            'nuclease_type': ['SpCas9'] * n_records,
            'gc_content': np.random.uniform(0.3, 0.7, n_records),
            'efficiency_score': np.random.uniform(0.6, 1.0, n_records)
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_large_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=n_records,
            organism="human"
        )
        
        # Execute validation
        import time
        start = time.time()
        report = await orchestrator.validate_dataset(dataset, metadata)
        duration = time.time() - start
        
        # Verify completion
        assert 'final_decision' in report
        
        # Verify performance target (<15s for 1000 records)
        assert duration < 15.0
        
        # Verify all records processed
        assert report['stages']['schema']['records_processed'] == n_records
    
    # ===== HUMAN REVIEW WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_human_review_triggered_workflow(self, orchestrator):
        """Test workflow that triggers human review"""
        # Create dataset with ambiguous issues
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['UNKNOWN_GENE_XYZ', 'AMBIGUOUS_SYMBOL'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9']
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_review_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=2,
            organism="human"
        )
        
        # Execute validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Should trigger human review
        assert report['requires_human_review'] is True
    
    # ===== SHORT-CIRCUIT WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_short_circuit_workflow(self, orchestrator):
        """Test short-circuit behavior on critical failure"""
        # Create dataset with critical schema failure
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001']
            # Missing all required fields
        })
        
        metadata = DatasetMetadata(
            dataset_id="e2e_shortcircuit_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=1,
            organism="human"
        )
        
        # Execute validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Should short-circuit
        assert report['short_circuited'] is True
        assert report['final_decision'] == Decision.REJECTED
        
        # Later stages should be skipped
        if 'bio_lookups' in report['stages']:
            assert report['stages']['bio_lookups'].get('skipped', False) is True
    
    # ===== MULTI-FORMAT WORKFLOWS =====
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.parametrize("format_type", [
        FormatType.GUIDE_RNA,
        FormatType.FASTA,
        FormatType.GENBANK
    ])
    async def test_multiple_format_workflows(self, orchestrator, format_type):
        """Test workflows with different data formats"""
        # Create appropriate dataset for format
        if format_type == FormatType.GUIDE_RNA:
            dataset = pd.DataFrame({
                'guide_id': ['gRNA_001'],
                'sequence': ['ATCGATCGATCGATCGATCG'],
                'pam_sequence': ['AGG'],
                'target_gene': ['BRCA1'],
                'organism': ['human'],
                'nuclease_type': ['SpCas9']
            })
        else:
            # Minimal dataset for other formats
            dataset = pd.DataFrame({
                'id': ['seq_001'],
                'sequence': ['ATCGATCGATCGATCGATCG']
            })
        
        metadata = DatasetMetadata(
            dataset_id=f"e2e_format_{format_type.value}",
            format_type=format_type,
            record_count=len(dataset),
            organism="human"
        )
        
        # Execute validation
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Should complete
        assert 'final_decision' in report


class TestEndToEndScenarios:
    """Real-world scenario tests"""
    
    @pytest.fixture
    def orchestrator(self):
        return ValidationOrchestrator()
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_crispr_screening_experiment_workflow(self, orchestrator):
        """Test workflow for CRISPR screening experiment"""
        # Simulate real screening library
        genes = ['BRCA1', 'TP53', 'EGFR', 'KRAS', 'MYC'] * 10
        dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(50)],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 50,
            'pam_sequence': ['AGG'] * 50,
            'target_gene': genes,
            'organism': ['human'] * 50,
            'nuclease_type': ['SpCas9'] * 50,
            'gc_content': [0.5] * 50,
            'efficiency_score': [0.85] * 50,
            'predicted_off_targets': [2] * 50
        })
        
        metadata = DatasetMetadata(
            dataset_id="screening_lib_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=50,
            organism="human",
            experiment_type="pooled_screening"
        )
        
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        assert report['final_decision'] in [Decision.ACCEPTED, Decision.CONDITIONAL_ACCEPT]
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_therapeutic_development_workflow(self, orchestrator):
        """Test strict validation for therapeutic development"""
        # Therapeutic-grade gRNAs require higher standards
        dataset = pd.DataFrame({
            'guide_id': ['therapeutic_gRNA_001', 'therapeutic_gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'pam_sequence': ['AGG', 'TGG'],
            'target_gene': ['BRCA1', 'BRCA1'],
            'organism': ['human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9'],
            'gc_content': [0.55, 0.52],
            'efficiency_score': [0.95, 0.93],
            'predicted_off_targets': [0, 0],  # Must have zero off-targets
            'validation_status': ['wet_lab_validated', 'wet_lab_validated']
        })
        
        metadata = DatasetMetadata(
            dataset_id="therapeutic_001",
            format_type=FormatType.GUIDE_RNA,
            record_count=2,
            organism="human",
            quality_tier="clinical_grade"
        )
        
        report = await orchestrator.validate_dataset(dataset, metadata)
        
        # Therapeutic data should have stricter validation
        assert 'final_decision' in report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])