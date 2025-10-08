# src/utils/bio_tools.py
"""
Bioinformatics utility functions.
"""
from typing import Dict, List, Optional, Tuple
from Bio import SeqIO, Seq
from Bio.SeqUtils import GC
import re


def calculate_gc_content(sequence: str) -> float:
    """
    Calculate GC content of a sequence.
    
    Args:
        sequence: DNA/RNA sequence string
        
    Returns:
        GC content as float between 0 and 1
    """
    if not sequence:
        return 0.0
    
    seq_upper = sequence.upper()
    gc_count = seq_upper.count('G') + seq_upper.count('C')
    return gc_count / len(sequence)


def validate_dna_sequence(sequence: str) -> bool:
    """Validate DNA sequence contains only valid characters"""
    return bool(re.match(r'^[ATCGN]+$', sequence.upper()))


def validate_rna_sequence(sequence: str) -> bool:
    """Validate RNA sequence contains only valid characters"""
    return bool(re.match(r'^[AUCGN]+$', sequence.upper()))


def validate_protein_sequence(sequence: str) -> bool:
    """Validate protein sequence contains only valid characters"""
    return bool(re.match(r'^[ACDEFGHIKLMNPQRSTVWY*]+$', sequence.upper()))


def reverse_complement(sequence: str) -> str:
    """
    Get reverse complement of DNA sequence.
    
    Args:
        sequence: DNA sequence
        
    Returns:
        Reverse complement sequence
    """
    seq_obj = Seq.Seq(sequence)
    return str(seq_obj.reverse_complement())


def translate_sequence(sequence: str, table: int = 1) -> str:
    """
    Translate DNA sequence to protein.
    
    Args:
        sequence: DNA sequence
        table: Translation table (default: 1 for standard genetic code)
        
    Returns:
        Protein sequence
    """
    seq_obj = Seq.Seq(sequence)
    return str(seq_obj.translate(table=table))


def detect_pam_sequence(
    guide_sequence: str,
    target_sequence: str,
    nuclease: str = "SpCas9"
) -> Optional[str]:
    """
    Detect PAM sequence for CRISPR guide.
    
    Args:
        guide_sequence: Guide RNA sequence
        target_sequence: Target genomic sequence
        nuclease: Nuclease type
        
    Returns:
        PAM sequence if found, None otherwise
    """
    # PAM patterns for different nucleases
    pam_patterns = {
        'SpCas9': r'[ATCG]GG',      # NGG
        'SaCas9': r'[ATCG]{2}GR[AG]T',  # NNGRRT
        'Cas12a': r'TTT[ATCG]',     # TTTV
    }
    
    pattern = pam_patterns.get(nuclease)
    if not pattern:
        return None
    
    # Search for guide sequence in target
    guide_pos = target_sequence.find(guide_sequence)
    if guide_pos == -1:
        return None
    
    # Extract potential PAM sequence
    pam_start = guide_pos + len(guide_sequence)
    if pam_start + 3 <= len(target_sequence):
        potential_pam = target_sequence[pam_start:pam_start + 3]
        if re.match(pattern, potential_pam):
            return potential_pam
    
    return None


def calculate_melting_temperature(
    sequence: str,
    na_conc: float = 50.0,
    mg_conc: float = 1.5
) -> float:
    """
    Calculate melting temperature using nearest-neighbor method.
    Simplified implementation.
    
    Args:
        sequence: DNA sequence
        na_conc: Sodium concentration (mM)
        mg_conc: Magnesium concentration (mM)
        
    Returns:
        Melting temperature in Celsius
    """
    # Simplified Wallace rule for short sequences
    if len(sequence) < 14:
        at_count = sequence.upper().count('A') + sequence.upper().count('T')
        gc_count = sequence.upper().count('G') + sequence.upper().count('C')
        return 2 * at_count + 4 * gc_count
    
    # More accurate for longer sequences
    gc = calculate_gc_content(sequence)
    return 64.9 + 41 * (gc - 16.4 / len(sequence))


def find_restriction_sites(
    sequence: str,
    enzyme: str = "EcoRI"
) -> List[int]:
    """
    Find restriction enzyme sites in sequence.
    
    Args:
        sequence: DNA sequence
        enzyme: Restriction enzyme name
        
    Returns:
        List of positions where enzyme cuts
    """
    # Common restriction enzyme sites
    enzyme_sites = {
        'EcoRI': 'GAATTC',
        'BamHI': 'GGATCC',
        'HindIII': 'AAGCTT',
        'PstI': 'CTGCAG',
        'SmaI': 'CCCGGG',
    }
    
    site = enzyme_sites.get(enzyme)
    if not site:
        return []
    
    positions = []
    start = 0
    while True:
        pos = sequence.find(site, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    
    return positions


def check_off_targets(
    guide_sequence: str,
    max_mismatches: int = 3
) -> Dict[str, any]:
    """
    Check for potential off-target sites.
    Simplified implementation - in production would use BLAST or similar.
    
    Args:
        guide_sequence: Guide RNA sequence
        max_mismatches: Maximum allowed mismatches
        
    Returns:
        Dict with off-target analysis
    """
    # This is a placeholder - real implementation would:
    # 1. BLAST against genome
    # 2. Calculate mismatch positions
    # 3. Score off-target likelihood
    
    return {
        "potential_off_targets": 0,
        "max_mismatches_checked": max_mismatches,
        "analysis_method": "placeholder"
    }