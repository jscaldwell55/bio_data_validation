# src/schemas/biological_schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional
import re

class SequenceRecord(BaseModel):
    """Schema for biological sequence records"""
    id: str = Field(..., min_length=1, max_length=255)
    sequence: str = Field(..., min_length=1)
    sequence_type: str = Field(..., pattern="^(DNA|RNA|PROTEIN)$")
    organism: Optional[str] = None
    description: Optional[str] = None
    
    @validator('sequence')
    def validate_sequence(cls, v, values):
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
            raise ValueError(f"Invalid characters for {seq_type}: {invalid_chars}")
        
        return v

class GuideRNARecord(BaseModel):
    """Schema for CRISPR guide RNA data"""
    guide_id: str
    sequence: str = Field(..., min_length=18, max_length=24)
    pam_sequence: str = Field(..., pattern="^[ATCG]{2,3}$")
    target_gene: str
    organism: str
    nuclease_type: str = Field(default="SpCas9")
    efficiency_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    off_target_count: Optional[int] = Field(None, ge=0)
    
    @validator('sequence')
    def validate_guide_sequence(cls, v):
        v = v.upper()
        if not set(v).issubset(set('ATCGN')):
            raise ValueError("Guide RNA must contain only ATCG or N")
        return v
    
    @validator('pam_sequence')
    def validate_pam(cls, v, values):
        nuclease = values.get('nuclease_type', 'SpCas9')
        v = v.upper()
        
        # PAM validation rules for common nucleases
        pam_rules = {
            'SpCas9': r'^[ATCG]GG$',      # NGG
            'SaCas9': r'^[ATCG]{6}$',     # NNGRRT
            'Cas12a': r'^TTT[ATCG]$',     # TTTV
        }
        
        if nuclease in pam_rules:
            if not re.match(pam_rules[nuclease], v):
                raise ValueError(f"Invalid PAM for {nuclease}: {v}")
        
        return v