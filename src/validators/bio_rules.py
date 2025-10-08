# src/validators/bio_rules.py
import re
import time
from typing import List, Dict, Any, Union
import pandas as pd
import logging

from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class BioRulesValidator:
    """
    Local biological plausibility checks that don't require external API calls.
    Optimized for speed with vectorized operations where possible.
    """
    
    def __init__(self):
        # PAM sequence patterns for different nucleases
        self.pam_patterns = {
            'SpCas9': r'^[ATCG]GG$',      # NGG
            'SaCas9': r'^[ATCG]{2}G[AG][AG]T$',  # NNGRRT where R = A or G
            'Cas12a': r'^TTT[ATCG]$',     # TTTV
            'AsCas12a': r'^TTT[ATCG]$',   # TTTV
            'LbCas12a': r'^TTT[ATCG]$',   # TTTV
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
        
        # Only ERROR and CRITICAL cause validation to fail
        # WARNINGS are informational but don't fail validation
        has_critical_errors = any(
            i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
            for i in issues
        )
        
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
            passed=not has_critical_errors,
            severity=severity,
            issues=issues,
            execution_time_ms=execution_time,
            records_processed=len(df),
            metadata={"data_type": data_type}
        )
    
    def _validate_guide_rna_biology(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Vectorized biological validation for guide RNAs"""
        issues = []

        # Check for empty sequences (ERROR - data is invalid)
        if 'sequence' in df.columns:
            empty_seqs = df[df['sequence'].str.len() == 0]
            if not empty_seqs.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(empty_seqs)} empty sequences detected",
                    severity=ValidationSeverity.ERROR,
                    rule_id="BIO_006",
                    metadata={"count": len(empty_seqs)}
                ))

        # Check for invalid DNA characters (ERROR - data is invalid)
        if 'sequence' in df.columns:
            invalid_chars = df[~df['sequence'].str.upper().str.match(r'^[ATCGN]+$', na=False)]
            if not invalid_chars.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(invalid_chars)} sequences contain invalid DNA characters",
                    severity=ValidationSeverity.ERROR,
                    rule_id="BIO_007",
                    metadata={"count": len(invalid_chars)}
                ))

        # Check for RNA bases (Uracil) in DNA sequences (ERROR - wrong molecule type)
        if 'sequence' in df.columns:
            rna_in_dna = df[df['sequence'].str.contains('U', case=False, na=False)]
            if not rna_in_dna.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(rna_in_dna)} sequences contain uracil (U) - RNA base in DNA sequence",
                    severity=ValidationSeverity.ERROR,
                    rule_id="BIO_008",
                    metadata={"count": len(rna_in_dna)}
                ))

        # Validate guide length - split into critical and suboptimal
        if 'sequence' in df.columns:
            df['seq_length'] = df['sequence'].str.len()

            # Critically short guides (<15bp) - ERROR (unusable)
            critically_short = df[df['seq_length'] < 15]
            if not critically_short.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(critically_short)} guides are critically short (<15bp) - likely unusable",
                    severity=ValidationSeverity.ERROR,
                    rule_id="BIO_001A",
                    metadata={"count": len(critically_short)}
                ))

            # FIXED: Critically long guides (>30bp) - ERROR (unusable)
            critically_long = df[df['seq_length'] > 30]
            if not critically_long.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(critically_long)} guides are too long (>30bp) - likely unusable",
                    severity=ValidationSeverity.ERROR,
                    rule_id="BIO_001C",
                    metadata={"count": len(critically_long)}
                ))

            # Suboptimal length guides - WARNING (usable but suboptimal)
            # Either too short (15-18bp) or too long (21-30bp)
            suboptimal = df[((df['seq_length'] >= 15) & (df['seq_length'] < 19)) |
                           ((df['seq_length'] > 20) & (df['seq_length'] <= 30))]
            if not suboptimal.empty:
                issues.append(ValidationIssue(
                    field="sequence",
                    message=f"{len(suboptimal)} guides have suboptimal length (optimal: 19-20bp)",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIO_001B",
                    metadata={"count": len(suboptimal)}
                ))
        
        # Validate PAM sequences (vectorized where possible)
        if 'pam_sequence' in df.columns and 'nuclease_type' in df.columns:
            for nuclease, pattern in self.pam_patterns.items():
                nuclease_mask = df['nuclease_type'] == nuclease
                if nuclease_mask.any():
                    # FIXED: Use proper regex matching with upper case
                    invalid_pam = df[nuclease_mask & 
                                    ~df['pam_sequence'].str.upper().str.match(pattern, na=False)]
                    
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
        
        # FIXED: Check for poly-T stretches (vectorized) - case insensitive
        if 'sequence' in df.columns:
            poly_t = df[df['sequence'].str.upper().str.contains('TTTT', na=False)]
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
            homopolymer = df[df['sequence'].str.upper().str.contains(homopolymer_pattern, na=False)]
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
                                ~df['sequence'].str.upper().str.match(r'^[ATCGN]+$', na=False)]
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
                                ~df['sequence'].str.upper().str.match(r'^[AUCGN]+$', na=False)]
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
                                    ~df['sequence'].str.upper().str.match(r'^[ACDEFGHIKLMNPQRSTVWY*]+$', na=False)]
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


# Alias for backward compatibility
BioRules = BioRulesValidator