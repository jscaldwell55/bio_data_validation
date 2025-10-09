# src/schemas/biological_schemas.py
"""
Pydantic schemas for biological data validation.
Defines data models for sequences, guide RNAs, and other biological entities.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
import re


class SequenceRecord(BaseModel):
    """
    Schema for biological sequence records (DNA/RNA/Protein).
    
    Validates sequence alphabet based on sequence_type.
    """
    id: str = Field(..., min_length=1, max_length=255, description="Unique sequence identifier")
    sequence: str = Field(..., min_length=1, description="Biological sequence string")
    sequence_type: str = Field(..., pattern="^(DNA|RNA|PROTEIN)$", description="Type of sequence")
    organism: Optional[str] = Field(None, description="Source organism")
    description: Optional[str] = Field(None, description="Sequence description")
    
    @validator('sequence')
    def validate_sequence(cls, v, values):
        """Validate sequence contains only valid characters for its type"""
        seq_type = values.get('sequence_type')
        v = v.upper().strip()
        
        if seq_type == 'DNA':
            valid_chars = set('ATCGN')
        elif seq_type == 'RNA':
            valid_chars = set('AUCGN')
        elif seq_type == 'PROTEIN':
            valid_chars = set('ACDEFGHIKLMNPQRSTVWY*')
        else:
            raise ValueError(f"Unknown sequence type: {seq_type}")
        
        invalid_chars = set(v) - valid_chars
        if invalid_chars:
            raise ValueError(
                f"Invalid characters for {seq_type} sequence: {invalid_chars}. "
                f"Valid characters: {sorted(valid_chars)}"
            )
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "seq_001",
                "sequence": "ATCGATCGATCG",
                "sequence_type": "DNA",
                "organism": "Homo sapiens",
                "description": "Example DNA sequence"
            }
        }


class GuideRNARecord(BaseModel):
    """
    Schema for CRISPR guide RNA data.
    
    Validates:
    - Guide sequence length (18-24 bp for most nucleases)
    - PAM sequence format for specific nucleases
    - DNA alphabet compliance
    - Efficiency scores and off-target counts
    """
    guide_id: str = Field(..., description="Unique guide RNA identifier")
    sequence: str = Field(
        ..., 
        min_length=18, 
        max_length=24,
        description="Guide RNA sequence (18-24 bp)"
    )
    pam_sequence: str = Field(
        ..., 
        pattern="^[ATCG]{2,6}$",  # Allow 2-6 bases for different nucleases
        description="Protospacer Adjacent Motif sequence"
    )
    target_gene: str = Field(..., description="Target gene symbol")
    organism: str = Field(..., description="Target organism")
    nuclease_type: str = Field(
        default="SpCas9",
        description="CRISPR nuclease type (SpCas9, SaCas9, Cas12a, etc.)"
    )
    efficiency_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0,
        description="Predicted on-target efficiency (0-1)"
    )
    off_target_count: Optional[int] = Field(
        None, 
        ge=0,
        description="Number of predicted off-target sites"
    )
    gc_content: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="GC content of guide sequence (0-1)"
    )
    
    @validator('sequence')
    def validate_guide_sequence(cls, v):
        """Validate guide sequence contains only DNA bases"""
        v = v.upper().strip()
        
        if not set(v).issubset(set('ATCGN')):
            invalid = set(v) - set('ATCGN')
            raise ValueError(
                f"Guide RNA must contain only ATCG or N (ambiguous base). "
                f"Invalid characters found: {invalid}"
            )
        
        return v
    
    @validator('pam_sequence')
    def validate_pam(cls, v, values):
        """
        Validate PAM sequence matches nuclease requirements.
        
        PAM patterns:
        - SpCas9: NGG (most common)
        - SaCas9: NNGRRT (where R = A or G)
        - Cas12a/AsCas12a/LbCas12a: TTTV (where V = A, C, or G)
        """
        nuclease = values.get('nuclease_type', 'SpCas9')
        v = v.upper().strip()
        
        # PAM validation rules for common nucleases
        pam_rules = {
            'SpCas9': (r'^[ATCG]GG$', 'NGG'),
            'SaCas9': (r'^[ATCG]{2}G[AG][AG]T$', 'NNGRRT'),  # FIXED: Proper NNGRRT pattern
            'Cas12a': (r'^TTT[ATCG]$', 'TTTV'),
            'AsCas12a': (r'^TTT[ATCG]$', 'TTTV'),
            'LbCas12a': (r'^TTT[ATCG]$', 'TTTV'),
        }
        
        if nuclease in pam_rules:
            pattern, description = pam_rules[nuclease]
            if not re.match(pattern, v):
                raise ValueError(
                    f"Invalid PAM sequence '{v}' for {nuclease}. "
                    f"Expected pattern: {description}"
                )
        else:
            # Unknown nuclease - just validate it's DNA
            if not set(v).issubset(set('ATCG')):
                raise ValueError(
                    f"PAM sequence must contain only ATCG. "
                    f"Found invalid characters: {set(v) - set('ATCG')}"
                )
        
        return v
    
    @validator('nuclease_type')
    def validate_nuclease_type(cls, v):
        """Validate nuclease type is recognized"""
        known_nucleases = {
            'SpCas9', 'SaCas9', 'Cas12a', 'AsCas12a', 'LbCas12a',
            'Cas13a', 'Cas13b', 'Cpf1'  # Additional common types
        }
        
        # Allow unknown nucleases but log warning
        if v not in known_nucleases:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Unknown nuclease type: {v}. "
                f"Known types: {sorted(known_nucleases)}"
            )
        
        return v
    
    @validator('target_gene')
    def validate_target_gene(cls, v):
        """Basic validation for gene symbols"""
        v = v.strip()
        
        if not v:
            raise ValueError("Target gene cannot be empty")
        
        # Gene symbols typically don't contain special characters except - and _
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Gene symbol '{v}' contains unusual characters. "
                f"This may cause issues with external database lookups."
            )
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "guide_id": "gRNA_001",
                "sequence": "ATCGATCGATCGATCGATCG",
                "pam_sequence": "AGG",
                "target_gene": "BRCA1",
                "organism": "human",
                "nuclease_type": "SpCas9",
                "efficiency_score": 0.85,
                "off_target_count": 2,
                "gc_content": 0.50
            }
        }


# =============================================================================
# Additional Biological Schemas (for future expansion)
# =============================================================================

class VariantRecord(BaseModel):
    """
    Schema for genetic variants (SNPs, indels, etc.).
    Future enhancement for variant validation.
    """
    variant_id: str = Field(..., description="Unique variant identifier")
    chromosome: str = Field(..., description="Chromosome identifier")
    position: int = Field(..., ge=1, description="Genomic position (1-based)")
    ref_allele: str = Field(..., description="Reference allele")
    alt_allele: str = Field(..., description="Alternate allele")
    variant_type: str = Field(..., description="SNP, insertion, deletion, etc.")
    
    class Config:
        json_schema_extra = {
            "example": {
                "variant_id": "rs1234567",
                "chromosome": "chr1",
                "position": 12345,
                "ref_allele": "A",
                "alt_allele": "G",
                "variant_type": "SNP"
            }
        }


class PrimerRecord(BaseModel):
    """
    Schema for PCR primers.
    Future enhancement for primer validation.
    """
    primer_id: str = Field(..., description="Unique primer identifier")
    sequence: str = Field(..., min_length=15, max_length=35, description="Primer sequence")
    melting_temp: Optional[float] = Field(None, ge=0, le=100, description="Melting temperature (°C)")
    gc_content: Optional[float] = Field(None, ge=0.0, le=1.0, description="GC content")
    
    @validator('sequence')
    def validate_primer_sequence(cls, v):
        """Validate primer sequence is DNA"""
        v = v.upper().strip()
        if not set(v).issubset(set('ATCGN')):
            raise ValueError("Primer must contain only DNA bases (ATCGN)")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "primer_id": "primer_F1",
                "sequence": "ATCGATCGATCGATCG",
                "melting_temp": 58.5,
                "gc_content": 0.50
            }
        }