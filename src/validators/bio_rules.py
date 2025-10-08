# src/validators/bio_rules.py
import re
import time
from typing import List, Dict, Any, Union
import pandas as pd
import logging

from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)

class BioRules:
    """
    Local biological plausibility checks that don't require external API calls.
    Optimized for speed with vectorized operations where possible.
    """
    
    def __init__(self):
        # PAM sequence patterns for different nucleases
        self.pam_patterns = {
            'SpCas9': r'[ATCG]GG',      # NGG
            'SaCas9': r'[ATCG]{2}GR[AG]T',  # NNGRRT
            'Cas12a': r'TTT[ATCG]',     # TTTV
            'AsCas12a': r'TTT[ATCG]',   # TTTV
            'LbCas12a': r'TTT[ATCG]',   # TTTV
        }
        
        # Optimal guide RNA lengths by nuclease
        self.optimal_lengths = {
            'SpCas9': (18, 20),
            'SaCas9': (21, 23),
            'Cas12a': (20, 24),
            'AsCas12a': (20, 24),
            'LbCas12a': (20, 24),
        }
    
    def validate(
        self,
        df: pd.DataFrame,
        data_type: str = 'guide_rna'
    ) -> ValidationResult:
        """
        Perform local biological validation checks.
        
        Args:
            df: DataFrame with biological data
            data_type: Type of biological data ('guide_rna', 'sequence', etc.)
            
        Returns:
            ValidationResult with detected issues
        """
        start_time = time.time()
        issues: List[ValidationIssue] = []
        
        try:
            if data_type == 'guide_rna':
                issues.extend(self._validate_guide_rna_biology(df))
            elif data_type == 'sequence':
                issues.extend(self._validate_sequence_biology(df))
            else:
                logger.warning(f"Unknown data type for bio rules: {data_type}")
        
        except Exception as e:
            logger.exception(f"Bio rules validation error: {str(e)}")
            issues.append(ValidationIssue(
                field="system",
                message=f"Bio rules validation error: {str(e)}",
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
            validator_name="BioRules",
            passed=not has_errors,
            severity=severity,
            issues=issues,
            execution_time_ms=execution_time,
            records_processed=len(df),
            metadata={"data_type": data_type}
        )
    
    def _validate_guide_rna_biology(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Vectorized biological validation for guide RNAs"""
        issues = []
        
        # Validate guide length for nuclease type (vectorized)
        if 'nuclease_type' in df.columns and 'sequence' in df.columns:
            df['seq_length'] = df['sequence'].str.len()
            
            for nuclease, (min_len, max_len) in self.optimal_lengths.items():
                nuclease_mask = df['nuclease_type'] == nuclease
                suboptimal = df[nuclease_mask & 
                               ((df['seq_length'] < min_len) | (df['seq_length'] > max_len))]
                
                if not suboptimal.empty:
                    issues.append(ValidationIssue(
                        field="sequence",
                        message=f"{len(suboptimal)} guides have suboptimal length for {nuclease} (optimal: {min_len}-{max_len}bp)",
                        severity=ValidationSeverity.WARNING,
                        rule_id="BIO_001",
                        metadata={"count": len(suboptimal), "nuclease": nuclease}
                    ))
        
        # Validate PAM sequences (vectorized where possible)
        if 'pam_sequence' in df.columns and 'nuclease_type' in df.columns:
            for nuclease, pattern in self.pam_patterns.items():
                nuclease_mask = df['nuclease_type'] == nuclease
                if nuclease_mask.any():
                    invalid_pam = df[nuclease_mask & 
                                    ~df['pam_sequence'].str.upper().str.match(pattern)]
                    
                    if not invalid_pam.empty:
                        issues.append(ValidationIssue(
                            field="pam_sequence",
                            message=f"{len(invalid_pam)} invalid PAM sequences for {nuclease}",
                            severity=ValidationSeverity.ERROR,
                            rule_id="BIO_002",
                            metadata={"count": len(invalid_pam), "nuclease": nuclease}
                        ))
        
        # Validate GC content (vectorized)
        if 'sequence' in df.columns:
            df['gc_content'] = df['sequence'].apply(self._calculate_gc_content)
            
            suboptimal_gc = df[(df['gc_content'] < 0.40) | (df['gc_content'] > 0.70)]
            if not suboptimal_gc.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(suboptimal_gc)} guides have suboptimal GC content (optimal: 40-70%)",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIO_003",
                    metadata={"count": len(suboptimal_gc)}
                ))
        
        # Check for poly-T stretches (vectorized)
        if 'sequence' in df.columns:
            poly_t = df[df['sequence'].str.contains('TTTT', case=False, na=False)]
            if not poly_t.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(poly_t)} guides contain poly-T stretch (TTTT), may cause transcription termination",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIO_004",
                    metadata={"count": len(poly_t)}
                ))
        
        # Check for homopolymer runs (vectorized)
        if 'sequence' in df.columns:
            homopolymer_pattern = r'([ATCG])\1{4,}'
            homopolymer = df[df['sequence'].str.contains(homopolymer_pattern, case=False, na=False)]
            if not homopolymer.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(homopolymer)} guides contain homopolymer runs (5+ identical bases)",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIO_005",
                    metadata={"count": len(homopolymer)}
                ))
        
        return issues
    
    def _validate_sequence_biology(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Biological validation for general sequences"""
        issues = []
        
        if 'sequence' in df.columns and 'sequence_type' in df.columns:
            # Validate sequence alphabet (vectorized)
            dna_mask = df['sequence_type'] == 'DNA'
            rna_mask = df['sequence_type'] == 'RNA'
            protein_mask = df['sequence_type'] == 'PROTEIN'
            
            # DNA validation
            if dna_mask.any():
                invalid_dna = df[dna_mask & 
                                ~df['sequence'].str.upper().str.match(r'^[ATCGN]+$')]
                if not invalid_dna.empty:
                    issues.append(ValidationIssue(
                        field="sequence",
                        message=f"{len(invalid_dna)} DNA sequences contain invalid characters",
                        severity=ValidationSeverity.ERROR,
                        rule_id="BIO_006"
                    ))
            
            # RNA validation
            if rna_mask.any():
                invalid_rna = df[rna_mask & 
                                ~df['sequence'].str.upper().str.match(r'^[AUCGN]+$')]
                if not invalid_rna.empty:
                    issues.append(ValidationIssue(
                        field="sequence",
                        message=f"{len(invalid_rna)} RNA sequences contain invalid characters",
                        severity=ValidationSeverity.ERROR,
                        rule_id="BIO_007"
                    ))
            
            # Protein validation
            if protein_mask.any():
                invalid_protein = df[protein_mask & 
                                    ~df['sequence'].str.upper().str.match(r'^[ACDEFGHIKLMNPQRSTVWY*]+$')]
                if not invalid_protein.empty:
                    issues.append(ValidationIssue(
                        field="sequence",
                        message=f"{len(invalid_protein)} protein sequences contain invalid characters",
                        severity=ValidationSeverity.ERROR,
                        rule_id="BIO_008"
                    ))
        
        return issues
    
    @staticmethod
    def _calculate_gc_content(sequence: str) -> float:
        """Calculate GC content of a sequence"""
        if not sequence:
            return 0.0
        seq_upper = sequence.upper()
        gc_count = seq_upper.count('G') + seq_upper.count('C')
        return gc_count / len(sequence)