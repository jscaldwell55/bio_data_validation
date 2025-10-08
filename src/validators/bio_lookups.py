# src/validators/bio_lookups.py
import time
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import pandas as pd
import logging
from collections import defaultdict

from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity
from src.utils.batch_processor import BatchProcessor

logger = logging.getLogger(__name__)


class NCBIClient:
    """Client for NCBI API interactions"""

    def __init__(self, api_key: Optional[str] = None, rate_limit: float = 0.34):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    async def get_gene_info(
        self,
        gene_symbol: str,
        organism: str = 'human'
    ) -> Optional[Dict[str, Any]]:
        """Look up gene information from NCBI Gene database"""
        params = {
            "db": "gene",
            "term": f"{gene_symbol}[Gene Name] AND {organism}[Organism]",
            "retmode": "json"
        }

        if self.api_key:
            params["api_key"] = self.api_key

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/esearch.fcgi",
                    params=params
                ) as response:
                    data = await response.json()
                    count = int(data['esearchresult']['count'])

                    if count > 0:
                        return {
                            'gene_id': data['esearchresult']['idlist'][0] if data['esearchresult']['idlist'] else None,
                            'symbol': gene_symbol,
                            'organism': organism,
                            'count': count
                        }
                    return None
        except Exception as e:
            logger.error(f"Error fetching gene info for {gene_symbol}: {str(e)}")
            return None


class EnsemblClient:
    """Client for Ensembl API interactions"""

    def __init__(self, batch_size: int = 50):
        self.batch_size = batch_size
        self.base_url = "https://rest.ensembl.org"

    async def get_gene_info(
        self,
        gene_symbol: str,
        species: str = 'homo_sapiens'
    ) -> Optional[Dict[str, Any]]:
        """Look up gene information from Ensembl"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/lookup/symbol/{species}/{gene_symbol}"
                headers = {"Content-Type": "application/json"}

                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Error fetching gene info from Ensembl for {gene_symbol}: {str(e)}")
            return None


# FIXED: Added class alias for backward compatibility
class BioLookupsValidator:
    """
    External biological database lookups with batching and rate limiting.
    Handles validation against NCBI, Ensembl, and other authoritative sources.
    """
    
    def __init__(
        self,
        ncbi_api_key: Optional[str] = None,
        ncbi_batch_size: int = 100,
        ncbi_rate_limit: float = 0.34,  # seconds between requests
        ensembl_batch_size: int = 50
    ):
        self.ncbi_api_key = ncbi_api_key
        self.ncbi_batch_size = ncbi_batch_size
        self.ncbi_rate_limit = ncbi_rate_limit
        self.ensembl_batch_size = ensembl_batch_size
        
        self.ncbi_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.ensembl_base_url = "https://rest.ensembl.org"
    
    async def validate(
        self,
        df: pd.DataFrame,
        validation_type: str = 'gene_symbols'
    ) -> ValidationResult:
        """
        Perform external database validation with batching.
        
        Args:
            df: DataFrame with biological identifiers
            validation_type: Type of validation ('gene_symbols', 'protein_ids', etc.)
            
        Returns:
            ValidationResult with lookup results
        """
        start_time = time.time()
        issues: List[ValidationIssue] = []
        
        try:
            if validation_type == 'gene_symbols':
                issues.extend(await self._validate_gene_symbols(df))
            elif validation_type == 'protein_ids':
                issues.extend(await self._validate_protein_ids(df))
            else:
                logger.warning(f"Unknown validation type: {validation_type}")
        
        except Exception as e:
            logger.exception(f"Bio lookups validation error: {str(e)}")
            issues.append(ValidationIssue(
                field="system",
                message=f"Bio lookups validation error: {str(e)}",
                severity=ValidationSeverity.CRITICAL
            ))
        
        execution_time = (time.time() - start_time) * 1000
        
        has_errors = any(i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                        for i in issues)
        
        if any(i.severity == ValidationSeverity.CRITICAL for i in issues):
            severity = ValidationSeverity.CRITICAL
        elif any(i.severity == ValidationSeverity.ERROR for i in issues):
            severity = ValidationSeverity.ERROR
        elif any(i.severity == ValidationSeverity.WARNING for i in issues):
            severity = ValidationSeverity.WARNING
        else:
            severity = ValidationSeverity.INFO
        
        return ValidationResult(
            validator_name="BioLookups",
            passed=not has_errors,
            severity=severity,
            issues=issues,
            execution_time_ms=execution_time,
            records_processed=len(df),
            metadata={"validation_type": validation_type}
        )
    
    async def _validate_gene_symbols(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate gene symbols against NCBI Gene database with batching"""
        issues = []
        
        if 'target_gene' not in df.columns:
            return issues
        
        # Get unique gene symbols and organisms
        gene_organism_pairs = df[['target_gene', 'organism']].drop_duplicates()
        
        # Batch process gene validations
        batch_processor = BatchProcessor(
            batch_size=self.ncbi_batch_size,
            rate_limit=self.ncbi_rate_limit
        )
        
        validation_results = await batch_processor.process_batches(
            items=gene_organism_pairs.to_dict('records'),
            process_func=self._validate_gene_batch
        )
        
        # Analyze results
        invalid_genes = []
        ambiguous_genes = []
        
        for result in validation_results:
            gene = result['gene']
            organism = result['organism']
            
            if not result['valid']:
                invalid_genes.append(f"{gene} ({organism})")
            elif result['count'] > 1:
                ambiguous_genes.append(f"{gene} ({organism}): {result['count']} matches")
        
        if invalid_genes:
            issues.append(ValidationIssue(
                field="target_gene",
                message=f"{len(invalid_genes)} gene symbols not found in NCBI Gene",
                severity=ValidationSeverity.ERROR,
                rule_id="LOOKUP_001",
                metadata={"invalid_genes": invalid_genes[:10]}  # Limit to first 10
            ))
        
        if ambiguous_genes:
            issues.append(ValidationIssue(
                field="target_gene",
                message=f"{len(ambiguous_genes)} ambiguous gene symbols (multiple matches)",
                severity=ValidationSeverity.WARNING,
                rule_id="LOOKUP_002",
                metadata={"ambiguous_genes": ambiguous_genes[:10]}
            ))
        
        return issues
    
    async def _validate_gene_batch(
        self,
        batch: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Validate a batch of gene symbols via NCBI API"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for item in batch:
                gene = item['target_gene']
                organism = item.get('organism', 'human')
                
                params = {
                    "db": "gene",
                    "term": f"{gene}[Gene Name] AND {organism}[Organism]",
                    "retmode": "json"
                }
                
                if self.ncbi_api_key:
                    params["api_key"] = self.ncbi_api_key
                
                try:
                    async with session.get(
                        f"{self.ncbi_base_url}/esearch.fcgi",
                        params=params
                    ) as response:
                        data = await response.json()
                        count = int(data['esearchresult']['count'])
                        
                        results.append({
                            'gene': gene,
                            'organism': organism,
                            'valid': count > 0,
                            'count': count,
                            'ids': data['esearchresult'].get('idlist', [])
                        })
                
                except Exception as e:
                    logger.error(f"Error validating gene {gene}: {str(e)}")
                    results.append({
                        'gene': gene,
                        'organism': organism,
                        'valid': False,
                        'count': 0,
                        'error': str(e)
                    })
                
                # Rate limiting
                await asyncio.sleep(self.ncbi_rate_limit)
        
        return results
    
    async def _validate_protein_ids(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate protein IDs against NCBI Protein database"""
        issues = []
        
        if 'protein_id' not in df.columns:
            return issues
        
        unique_ids = df['protein_id'].unique().tolist()
        
        # Batch process protein validations
        batch_processor = BatchProcessor(
            batch_size=self.ncbi_batch_size,
            rate_limit=self.ncbi_rate_limit
        )
        
        validation_results = await batch_processor.process_batches(
            items=unique_ids,
            process_func=self._validate_protein_batch
        )
        
        # Analyze results
        invalid_ids = [r['id'] for r in validation_results if not r['valid']]
        
        if invalid_ids:
            issues.append(ValidationIssue(
                field="protein_id",
                message=f"{len(invalid_ids)} protein IDs not found in NCBI Protein",
                severity=ValidationSeverity.ERROR,
                rule_id="LOOKUP_003",
                metadata={"invalid_ids": invalid_ids[:10]}
            ))
        
        return issues
    
    async def _validate_protein_batch(
        self,
        batch: List[str]
    ) -> List[Dict[str, Any]]:
        """Validate a batch of protein IDs"""
        results = []
        
        async with aiohttp.ClientSession() as session:
            # Build batch query
            id_list = ",".join(batch)
            
            params = {
                "db": "protein",
                "id": id_list,
                "retmode": "json"
            }
            
            if self.ncbi_api_key:
                params["api_key"] = self.ncbi_api_key
            
            try:
                async with session.get(
                    f"{self.ncbi_base_url}/esummary.fcgi",
                    params=params
                ) as response:
                    data = await response.json()
                    
                    # Check which IDs were found
                    found_ids = set(data.get('result', {}).get('uids', []))
                    
                    for protein_id in batch:
                        results.append({
                            'id': protein_id,
                            'valid': protein_id in found_ids
                        })
            
            except Exception as e:
                logger.error(f"Error validating protein batch: {str(e)}")
                for protein_id in batch:
                    results.append({
                        'id': protein_id,
                        'valid': False,
                        'error': str(e)
                    })
        
        return results


# Alias for backward compatibility
BioLookups = BioLookupsValidator