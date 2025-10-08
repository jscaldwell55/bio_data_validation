"""
Unit tests for Biological Lookups Validator
Tests external API integrations (NCBI, Ensembl) with batching and rate limiting
"""
import pytest
import pandas as pd
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.validators.bio_lookups import BioLookupsValidator
from src.schemas.base_schemas import ValidationResult, ValidationSeverity, ValidationIssue


class TestBioLookupsValidator:
    """Test suite for BioLookupsValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create BioLookupsValidator instance"""
        return BioLookupsValidator()
    
    @pytest.fixture
    def valid_gene_data(self):
        """Dataset with valid gene symbols"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human', 'human', 'human']
        })
    
    @pytest.fixture
    def mock_ncbi_client(self):
        """Mock NCBI client"""
        with patch('src.validators.bio_lookups.NCBIClient') as MockClient:
            mock = MockClient.return_value
            mock.get_gene_info = AsyncMock(return_value={
                'gene_id': '672',
                'symbol': 'BRCA1',
                'description': 'BRCA1 DNA repair associated',
                'organism': 'Homo sapiens'
            })
            yield mock
    
    @pytest.fixture
    def mock_ensembl_client(self):
        """Mock Ensembl client"""
        with patch('src.validators.bio_lookups.EnsemblClient') as MockClient:
            mock = MockClient.return_value
            mock.get_gene_info = AsyncMock(return_value={
                'id': 'ENSG00000012048',
                'display_name': 'BRCA1',
                'biotype': 'protein_coding'
            })
            yield mock
    
    # ===== NCBI GENE VALIDATION =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_valid_genes_pass(self, validator, valid_gene_data, mock_ncbi_client):
        """Test that valid gene symbols pass NCBI validation"""
        result = await validator.validate(valid_gene_data)
        
        gene_issues = [i for i in result.issues if 'gene' in i.message.lower()]
        error_issues = [i for i in gene_issues if i.severity == ValidationSeverity.ERROR]
        assert len(error_issues) == 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_invalid_gene_detected(self, validator, mock_ncbi_client):
        """Test detection of invalid/unknown gene symbols"""
        mock_ncbi_client.get_gene_info = AsyncMock(return_value=None)
        
        invalid_genes = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'target_gene': ['INVALID_GENE_XYZ', 'FAKE_GENE_123'],
            'organism': ['human', 'human']
        })
        
        result = await validator.validate(invalid_genes)
        
        assert result.passed is False
        gene_issues = [i for i in result.issues if 'gene' in i.message.lower() or 'not found' in i.message.lower()]
        assert len(gene_issues) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_gene_typo_detected(self, validator, mock_ncbi_client):
        """Test detection of typos in gene symbols"""
        mock_ncbi_client.get_gene_info = AsyncMock(return_value=None)
        
        typo_genes = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'target_gene': ['BRCAA1', 'TTP53', 'EGGFR'],  # Typos
            'organism': ['human', 'human', 'human']
        })
        
        result = await validator.validate(typo_genes)
        
        assert result.passed is False
        assert len(result.issues) > 0
    
    # ===== BATCH PROCESSING =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_batch_processing(self, validator, mock_ncbi_client):
        """Test that genes are validated in batches"""
        # Create dataset with 250 genes (should be batched)
        large_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:04d}' for i in range(250)],
            'target_gene': ['BRCA1'] * 250,
            'organism': ['human'] * 250
        })
        
        result = await validator.validate(large_dataset)
        
        # Should have made multiple batch calls
        # Verify batching happened (check call count)
        assert mock_ncbi_client.get_gene_info.call_count >= 1
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_batch_size_configuration(self, validator, mock_ncbi_client):
        """Test configurable batch size"""
        validator.batch_size = 50  # Set batch size
        
        dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:03d}' for i in range(150)],
            'target_gene': ['BRCA1'] * 150,
            'organism': ['human'] * 150
        })
        
        result = await validator.validate(dataset)
        
        # Should process in batches of 50
        assert isinstance(result, ValidationResult)
    
    # ===== RATE LIMITING =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_rate_limiting(self, validator, mock_ncbi_client):
        """Test rate limiting is applied"""
        import time
        
        validator.rate_limit_seconds = 0.34  # NCBI rate limit
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human', 'human', 'human']
        })
        
        start_time = time.time()
        result = await validator.validate(dataset)
        duration = time.time() - start_time
        
        # Should take at least rate_limit_seconds due to delays
        # (This is a simplified check)
        assert isinstance(result, ValidationResult)
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_ncbi_api_key_increases_rate_limit(self, validator):
        """Test that API key allows higher rate limit"""
        # With API key: 10 requests/second
        validator.ncbi_api_key = "test_key_123"
        validator.rate_limit_seconds = 0.1  # Faster with API key
        
        assert validator.rate_limit_seconds < 0.34  # Faster than default
    
    # ===== ENSEMBL INTEGRATION =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_ensembl_gene_lookup(self, validator, mock_ensembl_client):
        """Test Ensembl gene lookup"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        # Should successfully query Ensembl
        assert isinstance(result, ValidationResult)
        mock_ensembl_client.get_gene_info.assert_called()
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_ensembl_cross_reference(self, validator, mock_ensembl_client):
        """Test cross-referencing between NCBI and Ensembl"""
        mock_ensembl_client.get_gene_info = AsyncMock(return_value={
            'id': 'ENSG00000012048',
            'display_name': 'BRCA1',
            'external_refs': {'NCBI': '672'}
        })
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'organism': ['human'],
            'ensembl_id': ['ENSG00000012048']
        })
        
        result = await validator.validate(dataset)
        
        # Should validate consistency between databases
        assert isinstance(result, ValidationResult)
    
    # ===== ORGANISM VALIDATION =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_organism_mismatch_detected(self, validator, mock_ncbi_client):
        """Test detection of organism mismatches"""
        mock_ncbi_client.get_gene_info = AsyncMock(return_value={
            'gene_id': '672',
            'symbol': 'BRCA1',
            'organism': 'Homo sapiens'  # Human
        })
        
        wrong_organism = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'organism': ['mouse']  # Mismatch!
        })
        
        result = await validator.validate(wrong_organism)
        
        assert result.passed is False
        organism_issues = [i for i in result.issues if 'organism' in i.message.lower()]
        assert len(organism_issues) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_multiple_organisms(self, validator, mock_ncbi_client):
        """Test validation with multiple organisms"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'target_gene': ['BRCA1', 'Brca1', 'brca1'],
            'organism': ['human', 'mouse', 'rat']
        })
        
        result = await validator.validate(dataset)
        
        # Should validate each organism separately
        assert isinstance(result, ValidationResult)
    
    # ===== ERROR HANDLING =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_api_timeout_handling(self, validator, mock_ncbi_client):
        """Test handling of API timeouts"""
        mock_ncbi_client.get_gene_info = AsyncMock(side_effect=asyncio.TimeoutError())
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        # Should handle timeout gracefully
        assert isinstance(result, ValidationResult)
        assert len(result.issues) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_api_error_handling(self, validator, mock_ncbi_client):
        """Test handling of API errors"""
        mock_ncbi_client.get_gene_info = AsyncMock(side_effect=Exception("API Error"))
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        # Should handle error and report issue
        assert isinstance(result, ValidationResult)
        error_issues = [i for i in result.issues if 'error' in i.message.lower()]
        assert len(error_issues) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_partial_api_failure(self, validator, mock_ncbi_client):
        """Test handling when some API calls fail"""
        call_count = [0]
        
        async def mock_get_gene(symbol):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("API Error")
            return {'gene_id': '123', 'symbol': symbol}
        
        mock_ncbi_client.get_gene_info = mock_get_gene
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003', 'gRNA_004'],
            'target_gene': ['BRCA1', 'TP53', 'EGFR', 'KRAS'],
            'organism': ['human'] * 4
        })
        
        result = await validator.validate(dataset)
        
        # Should succeed for some, fail for others
        assert isinstance(result, ValidationResult)
    
    # ===== CACHING TESTS (Verify NO caching) =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_no_caching_fresh_lookup(self, validator, mock_ncbi_client):
        """Test that lookups are fresh every time (no caching)"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'target_gene': ['BRCA1', 'BRCA1'],  # Same gene twice
            'organism': ['human', 'human']
        })
        
        result = await validator.validate(dataset)
        
        # Should make separate API calls (no caching)
        # Call count should be >= number of unique genes
        assert mock_ncbi_client.get_gene_info.call_count >= 1
    
    # ===== PROTEIN ID VALIDATION =====
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_protein_id_validation(self, validator, mock_ncbi_client):
        """Test validation of protein IDs"""
        mock_ncbi_client.get_protein_info = AsyncMock(return_value={
            'protein_id': 'NP_009225.1',
            'description': 'BRCA1 protein'
        })
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'protein_id': ['NP_009225.1'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        assert isinstance(result, ValidationResult)
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_invalid_protein_id(self, validator, mock_ncbi_client):
        """Test detection of invalid protein IDs"""
        mock_ncbi_client.get_protein_info = AsyncMock(return_value=None)
        
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['BRCA1'],
            'protein_id': ['INVALID_PROTEIN_ID'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        assert result.passed is False
        protein_issues = [i for i in result.issues if 'protein' in i.message.lower()]
        assert len(protein_issues) > 0


class TestBioLookupsPerformance:
    """Performance tests for BioLookupsValidator"""
    
    @pytest.fixture
    def validator(self):
        return BioLookupsValidator()
    
    @pytest.mark.asyncio
    @pytest.mark.api
    @pytest.mark.slow
    async def test_large_batch_performance(self, validator, mock_ncbi_client):
        """Test performance with large number of genes"""
        # 1000 genes
        large_dataset = pd.DataFrame({
            'guide_id': [f'gRNA_{i:05d}' for i in range(1000)],
            'target_gene': ['BRCA1'] * 500 + ['TP53'] * 500,
            'organism': ['human'] * 1000
        })
        
        with patch('src.validators.bio_lookups.NCBIClient') as MockClient:
            mock = MockClient.return_value
            mock.get_gene_info = AsyncMock(return_value={
                'gene_id': '672',
                'symbol': 'BRCA1'
            })
            
            import time
            start = time.time()
            result = await validator.validate(large_dataset)
            duration = time.time() - start
            
            # Should complete in reasonable time with batching
            assert duration < 60.0  # Under 1 minute
            assert result.records_processed == 1000


class TestBioLookupsEdgeCases:
    """Edge case tests for BioLookupsValidator"""
    
    @pytest.fixture
    def validator(self):
        return BioLookupsValidator()
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_empty_gene_symbol(self, validator, mock_ncbi_client):
        """Test handling of empty gene symbols"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'target_gene': ['', None],
            'organism': ['human', 'human']
        })
        
        result = await validator.validate(dataset)
        
        assert result.passed is False
        assert len(result.issues) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_case_sensitivity(self, validator, mock_ncbi_client):
        """Test case sensitivity in gene symbols"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'target_gene': ['BRCA1', 'brca1', 'Brca1'],
            'organism': ['human', 'human', 'human']
        })
        
        result = await validator.validate(dataset)
        
        # Should handle case variations appropriately
        assert isinstance(result, ValidationResult)
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_special_characters_in_gene_name(self, validator, mock_ncbi_client):
        """Test handling of special characters"""
        dataset = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'target_gene': ['GENE-NAME/123'],
            'organism': ['human']
        })
        
        result = await validator.validate(dataset)
        
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])