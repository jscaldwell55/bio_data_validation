"""
Validator for genomic variant annotations (VCF data).

Validates:
- Variant nomenclature (HGVS format)
- Reference genome consistency
- Allele frequency plausibility
- Functional impact predictions
- dbSNP/ClinVar cross-references
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

from src.schemas.base_schemas import ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class VariantValidator:
    """
    Validates genomic variant callset data.
    
    Designed for VCF files and variant annotation tables used in
    precision medicine and population genomics studies.
    """
    
    # HGVS nomenclature patterns
    HGVS_GENOMIC = re.compile(
        r'^(?:chr)?([0-9]{1,2}|X|Y|MT):g\.(\d+)([ATCG]>)?([ATCG])$'
    )
    
    HGVS_CODING = re.compile(
        r'^([A-Z0-9_]+):c\.([*\-]?\d+)([\+\-]\d+)?([ATCG]>[ATCG]|del|ins|dup).*$'
    )
    
    HGVS_PROTEIN = re.compile(
        r'^([A-Z0-9_]+):p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter|\*)$'
    )
    
    # Valid reference genome builds
    VALID_BUILDS = ['GRCh37', 'hg19', 'GRCh38', 'hg38']
    
    # Functional impact terms (from VEP, SnpEff, etc.)
    VALID_CONSEQUENCES = {
        'transcript_ablation', 'splice_acceptor_variant',
        'splice_donor_variant', 'stop_gained', 'frameshift_variant',
        'stop_lost', 'start_lost', 'transcript_amplification',
        'inframe_insertion', 'inframe_deletion', 'missense_variant',
        'protein_altering_variant', 'splice_region_variant',
        'incomplete_terminal_codon_variant', 'start_retained_variant',
        'stop_retained_variant', 'synonymous_variant',
        'coding_sequence_variant', 'mature_miRNA_variant',
        '5_prime_UTR_variant', '3_prime_UTR_variant',
        'non_coding_transcript_exon_variant', 'intron_variant',
        'NMD_transcript_variant', 'non_coding_transcript_variant',
        'upstream_gene_variant', 'downstream_gene_variant',
        'TFBS_ablation', 'TFBS_amplification', 'TF_binding_site_variant',
        'regulatory_region_ablation', 'regulatory_region_amplification',
        'feature_elongation', 'regulatory_region_variant',
        'feature_truncation', 'intergenic_variant'
    }
    
    def __init__(self, reference_genome: str = "GRCh38"):
        """
        Initialize variant validator.
        
        Args:
            reference_genome: Reference genome build to validate against
        """
        if reference_genome not in self.VALID_BUILDS:
            logger.warning(
                f"Unknown reference genome: {reference_genome}. "
                f"Valid options: {self.VALID_BUILDS}"
            )
        
        self.reference_genome = reference_genome
        
        logger.info(
            f"VariantValidator initialized with reference: {reference_genome}"
        )
    
    def validate(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Validate variant annotation dataset.
        
        Args:
            df: DataFrame with variant data
            
        Returns:
            List of validation issues found
        """
        issues = []
        
        # Required columns check
        required_cols = ['chromosome', 'position', 'ref_allele', 'alt_allele']
        missing_cols = set(required_cols) - set(df.columns)
        
        if missing_cols:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                message=f"Missing required columns: {missing_cols}",
                field="schema",
                affected_records=0
            ))
            return issues  # Can't proceed without basic columns
        
        # Validate each check
        issues.extend(self._check_chromosome_format(df))
        issues.extend(self._check_position_validity(df))
        issues.extend(self._check_allele_format(df))
        issues.extend(self._check_hgvs_nomenclature(df))
        issues.extend(self._check_consequence_terms(df))
        issues.extend(self._check_allele_frequencies(df))
        issues.extend(self._check_reference_consistency(df))
        issues.extend(self._check_clinvar_assertions(df))
        
        return issues
    
    def _check_chromosome_format(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate chromosome naming consistency."""
        issues = []
        
        # Check for mixed 'chr' prefix usage
        has_chr_prefix = df['chromosome'].astype(str).str.startswith('chr')
        
        if has_chr_prefix.any() and not has_chr_prefix.all():
            mixed_count = (~has_chr_prefix).sum() if has_chr_prefix.sum() > len(df) / 2 else has_chr_prefix.sum()
            
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=(
                    "Inconsistent chromosome naming: some use 'chr' prefix, "
                    "others don't. This will cause issues in variant matching."
                ),
                field="chromosome",
                affected_records=int(mixed_count)
            ))
        
        # Check for invalid chromosome names
        valid_chroms = set([str(i) for i in range(1, 23)] + ['X', 'Y', 'MT', 'M'])
        valid_with_prefix = set(['chr' + c for c in valid_chroms])
        all_valid = valid_chroms | valid_with_prefix
        
        invalid_mask = ~df['chromosome'].astype(str).isin(all_valid)
        invalid_count = invalid_mask.sum()
        
        if invalid_count > 0:
            invalid_examples = df.loc[invalid_mask, 'chromosome'].unique()[:5]
            
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=(
                    f"Invalid chromosome names found: {list(invalid_examples)}. "
                    f"Must be 1-22, X, Y, MT/M (with optional 'chr' prefix)."
                ),
                field="chromosome",
                affected_records=int(invalid_count)
            ))
        
        return issues
    
    def _check_position_validity(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate genomic positions are plausible."""
        issues = []
        
        # Positions must be positive integers
        if not pd.api.types.is_integer_dtype(df['position']):
            try:
                df['position'] = df['position'].astype(int)
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    message="Position column contains non-integer values",
                    field="position",
                    affected_records=len(df)
                ))
                return issues
        
        # Check for negative or zero positions
        invalid_pos = (df['position'] <= 0)
        if invalid_pos.any():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Genomic positions must be positive integers",
                field="position",
                affected_records=int(invalid_pos.sum())
            ))
        
        # Check for implausibly large positions (beyond chromosome length)
        # Chromosome 1 is longest at ~250Mb
        implausible_pos = (df['position'] > 300_000_000)
        if implausible_pos.any():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=(
                    "Some positions exceed 300Mb, which is larger than any "
                    "human chromosome. Verify reference genome build."
                ),
                field="position",
                affected_records=int(implausible_pos.sum())
            ))
        
        return issues
    
    def _check_allele_format(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate allele format and sequences."""
        issues = []
        
        # Check for missing alleles
        for col in ['ref_allele', 'alt_allele']:
            missing = df[col].isna() | (df[col].astype(str) == '')
            if missing.any():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing {col} values",
                    field=col,
                    affected_records=int(missing.sum())
                ))
        
        # Check for invalid nucleotides
        valid_bases = set('ATCGN-')  # Including N for unknown, - for deletion
        
        for col in ['ref_allele', 'alt_allele']:
            invalid_mask = df[col].astype(str).apply(
                lambda x: not set(x.upper()).issubset(valid_bases)
            )
            
            if invalid_mask.any():
                invalid_examples = df.loc[invalid_mask, col].head(3).tolist()
                
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Invalid nucleotides in {col}: {invalid_examples}. "
                        f"Only ATCGN- allowed."
                    ),
                    field=col,
                    affected_records=int(invalid_mask.sum())
                ))
        
        # Check for suspiciously long indels (>50bp is unusual)
        if 'ref_allele' in df.columns and 'alt_allele' in df.columns:
            long_indel = (
                (df['ref_allele'].str.len() > 50) |
                (df['alt_allele'].str.len() > 50)
            )
            
            if long_indel.any():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    message=(
                        "Unusually long indels detected (>50bp). "
                        "Verify these are not annotation errors."
                    ),
                    field="ref_allele,alt_allele",
                    affected_records=int(long_indel.sum())
                ))
        
        return issues
    
    def _check_hgvs_nomenclature(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate HGVS notation if present."""
        issues = []
        
        if 'hgvs_c' not in df.columns and 'hgvs_p' not in df.columns:
            return issues  # Optional fields
        
        # Validate coding DNA notation
        if 'hgvs_c' in df.columns:
            non_empty = df['hgvs_c'].notna() & (df['hgvs_c'] != '')
            
            if non_empty.any():
                invalid = non_empty & ~df['hgvs_c'].apply(
                    lambda x: bool(self.HGVS_CODING.match(str(x)))
                )
                
                if invalid.any():
                    examples = df.loc[invalid, 'hgvs_c'].head(3).tolist()
                    
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Invalid HGVS coding notation: {examples}. "
                            f"Should follow format like NM_000546.6:c.215C>G"
                        ),
                        field="hgvs_c",
                        affected_records=int(invalid.sum())
                    ))
        
        # Validate protein notation
        if 'hgvs_p' in df.columns:
            non_empty = df['hgvs_p'].notna() & (df['hgvs_p'] != '')
            
            if non_empty.any():
                invalid = non_empty & ~df['hgvs_p'].apply(
                    lambda x: bool(self.HGVS_PROTEIN.match(str(x)))
                )
                
                if invalid.any():
                    examples = df.loc[invalid, 'hgvs_p'].head(3).tolist()
                    
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Invalid HGVS protein notation: {examples}. "
                            f"Should follow format like NP_000537.3:p.Arg72Pro"
                        ),
                        field="hgvs_p",
                        affected_records=int(invalid.sum())
                    ))
        
        return issues
    
    def _check_consequence_terms(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate variant consequence annotations."""
        issues = []
        
        if 'consequence' not in df.columns:
            return issues
        
        # Split multi-consequence annotations (VEP uses &)
        all_consequences = set()
        for consequences in df['consequence'].dropna():
            all_consequences.update(str(consequences).split('&'))
        
        # Check for invalid terms
        invalid_terms = all_consequences - self.VALID_CONSEQUENCES
        
        if invalid_terms:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Non-standard consequence terms found: {list(invalid_terms)[:5]}. "
                    f"These may not be recognized by downstream tools."
                ),
                field="consequence",
                affected_records=0  # Can't easily count
            ))
        
        return issues
    
    def _check_allele_frequencies(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate allele frequency values."""
        issues = []
        
        af_columns = [col for col in df.columns if 'AF' in col or 'frequency' in col.lower()]
        
        for col in af_columns:
            # Must be between 0 and 1
            out_of_range = (df[col] < 0) | (df[col] > 1)
            if out_of_range.any():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Allele frequencies in {col} must be between 0 and 1",
                    field=col,
                    affected_records=int(out_of_range.sum())
                ))
            
            # Suspicious if all variants are common (AF > 0.01)
            if (df[col] > 0.01).all():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"All variants in {col} have AF > 1%. "
                        f"This is unusual - verify filtering hasn't removed rare variants."
                    ),
                    field=col,
                    affected_records=len(df)
                ))
        
        return issues
    
    def _check_reference_consistency(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check for reference genome consistency issues."""
        issues = []
        
        if 'ref_genome' in df.columns:
            # Check for mixed reference genomes
            unique_refs = df['ref_genome'].unique()
            
            if len(unique_refs) > 1:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.CRITICAL,
                    message=(
                        f"Multiple reference genomes in dataset: {list(unique_refs)}. "
                        f"This will cause coordinate mismatches. "
                        f"All variants must use the same build."
                    ),
                    field="ref_genome",
                    affected_records=len(df)
                ))
            
            # Check if matches configured reference
            elif unique_refs[0] != self.reference_genome:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Dataset uses {unique_refs[0]} but validator configured "
                        f"for {self.reference_genome}. Coordinate mismatches may occur."
                    ),
                    field="ref_genome",
                    affected_records=len(df)
                ))
        
        return issues
    
    def _check_clinvar_assertions(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate ClinVar pathogenicity assertions if present."""
        issues = []
        
        if 'clinvar_significance' not in df.columns:
            return issues
        
        valid_assertions = {
            'Benign', 'Likely_benign', 'Uncertain_significance',
            'Likely_pathogenic', 'Pathogenic', 'drug_response',
            'association', 'risk_factor', 'protective', 'Affects',
            'conflicting_interpretations_of_pathogenicity', 'not_provided'
        }
        
        invalid_mask = ~df['clinvar_significance'].isin(valid_assertions)
        
        if invalid_mask.any():
            invalid_examples = df.loc[invalid_mask, 'clinvar_significance'].unique()[:5]
            
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Non-standard ClinVar assertions: {list(invalid_examples)}. "
                    f"Should be one of: {list(valid_assertions)[:5]}..."
                ),
                field="clinvar_significance",
                affected_records=int(invalid_mask.sum())
            ))
        
        return issues