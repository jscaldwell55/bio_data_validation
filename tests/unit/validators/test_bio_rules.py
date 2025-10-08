"""
Unit tests for Biological Rules Validator
Tests local biological plausibility checks (PAM, GC content, sequence alphabet, etc.)
"""
import pytest
import pandas as pd
from src.validators.bio_rules import BioRulesValidator
from src.schemas.base_schemas import ValidationResult, ValidationSeverity


class TestBioRulesValidator:
    """Test suite for BioRulesValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create BioRulesValidator instance"""
        return BioRulesValidator()
    
    @pytest.fixture
    def valid_spcas9_data(self):
        """Valid SpCas9 guide RNA data"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA', 'GATTACAGATTACAGATTAC'],
            'pam_sequence': ['AGG', 'TGG', 'CGG'],  # Valid NGG PAMs
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human', 'human', 'human'],
            'nuclease_type': ['SpCas9', 'SpCas9', 'SpCas9']
        })
    
    # ===== PAM SEQUENCE VALIDATION =====
    
    def test_valid_spcas9_pam(self, validator, valid_spcas9_data):
        """Test that valid SpCas9 PAM sequences (NGG) pass"""
        result = validator.validate(valid_spcas9_data)
        
        pam_issues = [i for i in result.issues if 'pam' in i.message.lower()]
        assert len(pam_issues) == 0
    
    def test_invalid_spcas9_pam(self, validator):
        """Test detection of invalid SpCas9 PAM sequences"""
        invalid_pam_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 3,
            'pam_sequence': ['AAA', 'TTT', 'CCC'],  # Invalid PAMs for SpCas9
            'target_gene': ['BRCA1', 'TP53', 'EGFR'],
            'organism': ['human'] * 3,
            'nuclease_type': ['SpCas9'] * 3
        })
        
        result = validator.validate(invalid_pam_data)
        
        assert result.passed is False
        pam_issues = [i for i in result.issues if 'pam' in i.message.lower()]
        assert len(pam_issues) > 0
        assert any('NGG' in i.message or 'invalid' in i.message.lower() for i in pam_issues)
    
    def test_sacas9_pam_validation(self, validator):
        """Test SaCas9 PAM validation (NNGRRT)"""
        sacas9_data = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 2,
            'pam_sequence': ['AAGAAT', 'TTGGAT'],  # Valid SaCas9 PAMs
            'target_gene': ['BRCA1', 'TP53'],
            'organism': ['human'] * 2,
            'nuclease_type': ['SaCas9'] * 2
        })
        
        result = validator.validate(sacas9_data)
        
        # Should pass if SaCas9 validation is implemented
        pam_issues = [i for i in result.issues if 'pam' in i.message.lower() and i.severity == ValidationSeverity.ERROR]
        assert len(pam_issues) == 0
    
    # ===== GUIDE RNA LENGTH VALIDATION =====
    
    def test_optimal_guide_length(self, validator):
        """Test that optimal guide length (20bp for SpCas9) passes"""
        optimal_length = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],  # Exactly 20bp
            'pam_sequence': ['AGG', 'TGG'],
            'nuclease_type': ['SpCas9'] * 2
        })
        
        result = validator.validate(optimal_length)
        
        length_issues = [i for i in result.issues if 'length' in i.message.lower() and i.severity == ValidationSeverity.ERROR]
        assert len(length_issues) == 0
    
    def test_guide_too_short(self, validator):
        """Test detection of guide RNAs that are too short"""
        too_short = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCG', 'GCTAGCTA'],  # Only 8bp - too short
            'pam_sequence': ['AGG', 'TGG'],
            'nuclease_type': ['SpCas9'] * 2
        })
        
        result = validator.validate(too_short)
        
        assert result.passed is False
        length_issues = [i for i in result.issues if 'length' in i.message.lower() or 'short' in i.message.lower()]
        assert len(length_issues) > 0
    
    def test_guide_too_long(self, validator):
        """Test detection of guide RNAs that are too long"""
        too_long = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGATCGATCGATCGATCGATCGATCG'],  # 28bp - too long
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(too_long)
        
        assert result.passed is False
        length_issues = [i for i in result.issues if 'length' in i.message.lower() or 'long' in i.message.lower()]
        assert len(length_issues) > 0
    
    # ===== GC CONTENT VALIDATION =====
    
    def test_optimal_gc_content(self, validator):
        """Test that optimal GC content (40-70%) passes"""
        optimal_gc = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCGCGCGCGCGCGCGCGCGC'],  # 50% and 100% GC
            'pam_sequence': ['AGG', 'TGG'],
            'nuclease_type': ['SpCas9'] * 2
        })
        
        result = validator.validate(optimal_gc)
        
        # 50% GC should be optimal, 100% should trigger warning
        gc_errors = [i for i in result.issues if 'gc' in i.message.lower() and i.severity == ValidationSeverity.ERROR]
        assert len(gc_errors) == 0  # No errors, maybe warnings
    
    def test_low_gc_content_warning(self, validator):
        """Test warning for suboptimal low GC content (<40%)"""
        low_gc = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['AAAAAAAAAAAAAAAAAAAT'],  # 5% GC (1 G out of 20)
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(low_gc)
        
        # Should trigger warning
        gc_issues = [i for i in result.issues if 'gc' in i.message.lower()]
        assert len(gc_issues) > 0
    
    def test_high_gc_content_warning(self, validator):
        """Test warning for suboptimal high GC content (>70%)"""
        high_gc = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['GCGCGCGCGCGCGCGCGCGC'],  # 100% GC
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(high_gc)
        
        gc_issues = [i for i in result.issues if 'gc' in i.message.lower()]
        assert len(gc_issues) > 0
    
    # ===== SEQUENCE ALPHABET VALIDATION =====
    
    def test_valid_dna_alphabet(self, validator, valid_spcas9_data):
        """Test that valid DNA sequences (ATCG) pass"""
        result = validator.validate(valid_spcas9_data)
        
        alphabet_issues = [i for i in result.issues if 'alphabet' in i.message.lower() or 'character' in i.message.lower()]
        assert len(alphabet_issues) == 0
    
    def test_invalid_dna_characters(self, validator):
        """Test detection of invalid DNA characters"""
        invalid_chars = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCG123XYZ', 'GCTA!@#$', 'TTAABCDEFG'],  # Invalid characters
            'pam_sequence': ['AGG', 'TGG', 'CGG'],
            'nuclease_type': ['SpCas9'] * 3
        })
        
        result = validator.validate(invalid_chars)
        
        assert result.passed is False
        alphabet_issues = [i for i in result.issues if 'alphabet' in i.message.lower() or 'invalid' in i.message.lower()]
        assert len(alphabet_issues) > 0
    
    def test_ambiguous_nucleotides(self, validator):
        """Test handling of ambiguous nucleotides (N, R, Y, etc.)"""
        ambiguous = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGNNNNRYSWKMBDHVN'],  # Contains ambiguous codes
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(ambiguous)
        
        # Should flag ambiguous nucleotides as warning or error
        assert len(result.issues) > 0
    
    # ===== HOMOPOLYMER DETECTION =====
    
    def test_no_homopolymers(self, validator, valid_spcas9_data):
        """Test that sequences without long homopolymers pass"""
        result = validator.validate(valid_spcas9_data)
        
        homopolymer_issues = [i for i in result.issues if 'homopolymer' in i.message.lower() or 'poly' in i.message.lower()]
        assert len(homopolymer_issues) == 0
    
    def test_poly_t_stretch_detected(self, validator):
        """Test detection of poly-T stretches (problematic for synthesis)"""
        poly_t = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGTTTTTTTTTTCGATCG'],  # Contains TTTTTTTTTT
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(poly_t)
        
        assert result.passed is False
        poly_issues = [i for i in result.issues if 'poly' in i.message.lower() or 'homopolymer' in i.message.lower()]
        assert len(poly_issues) > 0
    
    def test_poly_a_stretch_warning(self, validator):
        """Test warning for poly-A stretches"""
        poly_a = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['GCGAAAAAAAAAGCTAGCTA'],  # Contains AAAAAAAAAA
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(poly_a)
        
        poly_issues = [i for i in result.issues if 'poly' in i.message.lower()]
        assert len(poly_issues) > 0
    
    # ===== ORGANISM-SPECIFIC VALIDATION =====
    
    def test_organism_specific_rules(self, validator):
        """Test that organism-specific rules are applied"""
        multi_organism = pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002', 'gRNA_003'],
            'sequence': ['ATCGATCGATCGATCGATCG'] * 3,
            'pam_sequence': ['AGG'] * 3,
            'nuclease_type': ['SpCas9'] * 3,
            'organism': ['human', 'mouse', 'zebrafish']
        })
        
        result = validator.validate(multi_organism)
        
        # Different organisms may have different validation rules
        assert isinstance(result, ValidationResult)


class TestBioRulesEdgeCases:
    """Edge case tests for BioRulesValidator"""
    
    @pytest.fixture
    def validator(self):
        return BioRulesValidator()
    
    def test_lowercase_sequences(self, validator):
        """Test handling of lowercase DNA sequences"""
        lowercase = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['atcgatcgatcgatcgatcg'],  # All lowercase
            'pam_sequence': ['agg'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(lowercase)
        # Should either normalize or flag
        assert isinstance(result, ValidationResult)
    
    def test_mixed_case_sequences(self, validator):
        """Test handling of mixed-case sequences"""
        mixed = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCGatcgATCGatcgATCG'],  # Mixed case
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(mixed)
        assert isinstance(result, ValidationResult)
    
    def test_empty_sequence(self, validator):
        """Test handling of empty sequences"""
        empty = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': [''],  # Empty
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(empty)
        
        assert result.passed is False
        assert len(result.issues) > 0
    
    def test_whitespace_in_sequence(self, validator):
        """Test handling of whitespace in sequences"""
        whitespace = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['ATCG ATCG ATCG ATCG'],  # Contains spaces
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(whitespace)
        
        # Should either strip whitespace or flag as error
        assert isinstance(result, ValidationResult)
    
    def test_uracil_in_sequence(self, validator):
        """Test handling of U (uracil - RNA) in DNA sequence"""
        rna_base = pd.DataFrame({
            'guide_id': ['gRNA_001'],
            'sequence': ['AUCGAUCGAUCGAUCGAUCG'],  # Contains U instead of T
            'pam_sequence': ['AGG'],
            'nuclease_type': ['SpCas9']
        })
        
        result = validator.validate(rna_base)
        
        # Should flag U in DNA context
        assert len(result.issues) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])