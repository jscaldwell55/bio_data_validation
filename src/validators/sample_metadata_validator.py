"""
Validator for biological sample metadata.

Validates:
- Ontology compliance (UBERON, Cell Ontology, EFO)
- Unit validation (concentration, time, temperature)
- Experimental condition consistency
- Sample identifier format
- Batch effect tracking
"""

import re
import logging
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
import pandas as pd

from src.schemas.base_schemas import ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)


class SampleMetadataValidator:
    """
    Validates biological sample metadata for experimental datasets.
    
    Ensures metadata completeness, consistency, and ontology compliance
    for reproducible research.
    """
    
    # Common units and their valid patterns
    VALID_UNITS = {
        'concentration': {
            'M', 'mM', 'uM', 'nM', 'pM',  # Molarity
            'mg/ml', 'ug/ml', 'ng/ml',     # Mass concentration
            '%', 'v/v', 'w/v'               # Percentage
        },
        'time': {
            's', 'sec', 'seconds',
            'm', 'min', 'minutes',
            'h', 'hr', 'hours',
            'd', 'day', 'days',
            'w', 'week', 'weeks'
        },
        'temperature': {
            'C', '°C', 'celsius',
            'F', '°F', 'fahrenheit',
            'K', 'kelvin'
        },
        'volume': {
            'L', 'ml', 'ul', 'nl',
            'mL', 'μL', 'μl', 'nL'
        }
    }
    
    # Standard ontology prefixes
    ONTOLOGY_PREFIXES = {
        'UBERON': r'^UBERON:\d{7}$',        # Anatomy
        'CL': r'^CL:\d{7}$',                 # Cell type
        'EFO': r'^EFO:\d{7}$',               # Experimental factor
        'CHEBI': r'^CHEBI:\d+$',             # Chemical entities
        'NCIT': r'^NCIT:C\d+$',              # NCI Thesaurus
        'OBI': r'^OBI:\d{7}$',               # Ontology for Biomedical Investigations
        'UO': r'^UO:\d{7}$'                  # Units of measurement
    }
    
    # Required metadata fields
    CORE_FIELDS = {
        'sample_id',
        'organism',
        'tissue_type',
        'collection_date'
    }
    
    # Recommended fields
    RECOMMENDED_FIELDS = {
        'cell_type',
        'treatment',
        'time_point',
        'replicate_id',
        'batch_id',
        'experimenter'
    }
    
    def __init__(
        self,
        require_ontologies: bool = True,
        strict_units: bool = True
    ):
        """
        Initialize sample metadata validator.
        
        Args:
            require_ontologies: Enforce ontology term usage
            strict_units: Require standardized units
        """
        self.require_ontologies = require_ontologies
        self.strict_units = strict_units
        
        logger.info(
            f"SampleMetadataValidator initialized "
            f"(ontologies={require_ontologies}, strict_units={strict_units})"
        )
    
    def validate(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """
        Validate sample metadata dataset.
        
        Args:
            df: DataFrame with sample metadata
            
        Returns:
            List of validation issues
        """
        issues = []
        
        # Core validations
        issues.extend(self._check_required_fields(df))
        issues.extend(self._check_sample_id_format(df))
        issues.extend(self._check_organism_consistency(df))
        issues.extend(self._check_date_formats(df))
        issues.extend(self._check_ontology_terms(df))
        issues.extend(self._check_unit_consistency(df))
        issues.extend(self._check_batch_effects(df))
        issues.extend(self._check_duplicate_samples(df))
        issues.extend(self._check_missing_data_patterns(df))
        
        return issues
    
    def _check_required_fields(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check for required metadata fields."""
        issues = []
        
        missing_core = self.CORE_FIELDS - set(df.columns)
        
        if missing_core:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                message=(
                    f"Missing required metadata fields: {missing_core}. "
                    f"These are essential for reproducibility."
                ),
                field="schema",
                affected_records=len(df)
            ))
        
        # Check for recommended fields
        missing_recommended = self.RECOMMENDED_FIELDS - set(df.columns)
        
        if missing_recommended:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                message=(
                    f"Missing recommended fields: {missing_recommended}. "
                    f"Adding these improves metadata quality."
                ),
                field="schema",
                affected_records=0
            ))
        
        return issues
    
    def _check_sample_id_format(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate sample ID format and uniqueness."""
        issues = []
        
        if 'sample_id' not in df.columns:
            return issues
        
        # Check for missing IDs
        missing = df['sample_id'].isna() | (df['sample_id'] == '')
        if missing.any():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                message="Sample IDs are missing for some records",
                field="sample_id",
                affected_records=int(missing.sum())
            ))
        
        # Check for duplicates
        duplicates = df['sample_id'].duplicated(keep=False)
        if duplicates.any():
            dup_ids = df.loc[duplicates, 'sample_id'].unique()[:5]
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message=(
                    f"Duplicate sample IDs found: {list(dup_ids)}. "
                    f"Each sample must have a unique identifier."
                ),
                field="sample_id",
                affected_records=int(duplicates.sum())
            ))
        
        # Check for invalid characters
        invalid_chars_pattern = re.compile(r'[^\w\-\.]')
        has_invalid = df['sample_id'].astype(str).str.contains(
            invalid_chars_pattern,
            na=False
        )
        
        if has_invalid.any():
            examples = df.loc[has_invalid, 'sample_id'].head(3).tolist()
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Sample IDs contain special characters: {examples}. "
                    f"Use only alphanumeric, dash, underscore, and period."
                ),
                field="sample_id",
                affected_records=int(has_invalid.sum())
            ))
        
        return issues
    
    def _check_organism_consistency(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check organism field consistency."""
        issues = []
        
        if 'organism' not in df.columns:
            return issues
        
        # Check for missing
        missing = df['organism'].isna() | (df['organism'] == '')
        if missing.any():
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Organism not specified for some samples",
                field="organism",
                affected_records=int(missing.sum())
            ))
        
        # Check for inconsistent naming
        unique_organisms = df['organism'].dropna().unique()
        
        # Common naming variations
        variations = {
            'human': ['homo sapiens', 'human', 'h. sapiens', 'hsa'],
            'mouse': ['mus musculus', 'mouse', 'm. musculus', 'mmu'],
            'rat': ['rattus norvegicus', 'rat', 'r. norvegicus', 'rno']
        }
        
        for canonical, variants in variations.items():
            found_variants = [
                org for org in unique_organisms
                if org.lower() in variants
            ]
            
            if len(found_variants) > 1:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Inconsistent organism naming: {found_variants}. "
                        f"Standardize to '{canonical}' or use NCBI taxonomy ID."
                    ),
                    field="organism",
                    affected_records=0
                ))
        
        return issues
    
    def _check_date_formats(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate date field formats."""
        issues = []
        
        date_columns = [
            col for col in df.columns
            if 'date' in col.lower() or 'time' in col.lower()
        ]
        
        for col in date_columns:
            non_null = df[col].notna() & (df[col] != '')
            
            if not non_null.any():
                continue
            
            # Try parsing as datetime
            invalid_dates = []
            for val in df.loc[non_null, col].head(100):  # Check first 100
                try:
                    pd.to_datetime(val)
                except (ValueError, TypeError):
                    invalid_dates.append(val)
            
            if invalid_dates:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Invalid date format in {col}: {invalid_dates[:3]}. "
                        f"Use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)."
                    ),
                    field=col,
                    affected_records=len(invalid_dates)
                ))
        
        return issues
    
    def _check_ontology_terms(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Validate ontology term usage."""
        issues = []
        
        if not self.require_ontologies:
            return issues
        
        # Check tissue_type for UBERON terms
        if 'tissue_type' in df.columns:
            non_null = df['tissue_type'].notna() & (df['tissue_type'] != '')
            
            if non_null.any():
                uberon_pattern = re.compile(self.ONTOLOGY_PREFIXES['UBERON'])
                has_uberon = df.loc[non_null, 'tissue_type'].astype(str).str.match(uberon_pattern)
                
                if not has_uberon.all():
                    missing_ontology = (~has_uberon).sum()
                    examples = df.loc[non_null & ~has_uberon, 'tissue_type'].head(3).tolist()
                    
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        message=(
                            f"Tissue types not using UBERON ontology: {examples}. "
                            f"Consider using UBERON IDs for standardization "
                            f"(e.g., UBERON:0002107 for liver)."
                        ),
                        field="tissue_type",
                        affected_records=int(missing_ontology)
                    ))
        
        # Check cell_type for Cell Ontology terms
        if 'cell_type' in df.columns:
            non_null = df['cell_type'].notna() & (df['cell_type'] != '')
            
            if non_null.any():
                cl_pattern = re.compile(self.ONTOLOGY_PREFIXES['CL'])
                has_cl = df.loc[non_null, 'cell_type'].astype(str).str.match(cl_pattern)
                
                if not has_cl.all():
                    missing_ontology = (~has_cl).sum()
                    examples = df.loc[non_null & ~has_cl, 'cell_type'].head(3).tolist()
                    
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        message=(
                            f"Cell types not using Cell Ontology: {examples}. "
                            f"Use CL IDs for standardization (e.g., CL:0000066 for epithelial cell)."
                        ),
                        field="cell_type",
                        affected_records=int(missing_ontology)
                    ))
        
        return issues
    
    def _check_unit_consistency(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check for consistent units in measurement columns."""
        issues = []
        
        if not self.strict_units:
            return issues
        
        # Find columns that likely contain measurements
        measurement_patterns = [
            'concentration', 'dose', 'volume', 'temperature', 
            'time', 'duration', 'amount'
        ]
        
        for col in df.columns:
            col_lower = col.lower()
            
            # Skip if not a measurement column
            if not any(pattern in col_lower for pattern in measurement_patterns):
                continue
            
            # Extract unit type from column name
            unit_type = None
            for ut in self.VALID_UNITS.keys():
                if ut in col_lower:
                    unit_type = ut
                    break
            
            if not unit_type:
                continue
            
            # Check if values include units
            non_null = df[col].notna() & (df[col] != '')
            if not non_null.any():
                continue
            
            # Parse values for units
            values_with_units = df.loc[non_null, col].astype(str)
            
            # Extract units from values (e.g., "10 uM" -> "uM")
            found_units = set()
            for val in values_with_units.head(100):
                # Try to extract unit
                match = re.search(r'([a-zA-Z°μ/%]+)$', val.strip())
                if match:
                    found_units.add(match.group(1))
            
            # Check if units are valid
            valid_units = self.VALID_UNITS.get(unit_type, set())
            invalid_units = found_units - valid_units
            
            if invalid_units:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Non-standard units in {col}: {invalid_units}. "
                        f"Use standard units: {list(valid_units)[:5]}"
                    ),
                    field=col,
                    affected_records=0
                ))
            
            # Check for mixed units
            if len(found_units) > 1:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Mixed units in {col}: {found_units}. "
                        f"All measurements should use the same unit."
                    ),
                    field=col,
                    affected_records=int(non_null.sum())
                ))
        
        return issues
    
    def _check_batch_effects(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check for batch effect tracking."""
        issues = []
        
        # Check if batch_id exists
        if 'batch_id' not in df.columns:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                message=(
                    "No batch_id column found. Add batch tracking to "
                    "detect and correct for batch effects in analysis."
                ),
                field="schema",
                affected_records=0
            ))
            return issues
        
        # Check batch distribution
        batch_counts = df['batch_id'].value_counts()
        
        # Warn if batches are heavily imbalanced
        if len(batch_counts) > 1:
            max_batch = batch_counts.max()
            min_batch = batch_counts.min()
            ratio = max_batch / min_batch
            
            if ratio > 5:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Severe batch imbalance detected: "
                        f"largest batch is {ratio:.1f}x larger than smallest. "
                        f"This may confound biological signal with batch effects."
                    ),
                    field="batch_id",
                    affected_records=0
                ))
        
        # Check if batches correlate with biological conditions
        if 'treatment' in df.columns or 'condition' in df.columns:
            condition_col = 'treatment' if 'treatment' in df.columns else 'condition'
            
            # Check if each batch has multiple conditions
            batch_condition_counts = df.groupby('batch_id')[condition_col].nunique()
            
            single_condition_batches = (batch_condition_counts == 1).sum()
            
            if single_condition_batches > 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"{single_condition_batches} batches contain only one condition. "
                        f"Batch effects will be confounded with biological effects. "
                        f"Randomize samples across batches when possible."
                    ),
                    field="batch_id",
                    affected_records=0
                ))
        
        return issues
    
    def _check_duplicate_samples(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Check for duplicate biological samples."""
        issues = []
        
        # Define columns that should uniquely identify a sample
        identifying_cols = [
            col for col in ['sample_id', 'organism', 'tissue_type', 
                           'cell_type', 'treatment', 'time_point']
            if col in df.columns
        ]
        
        if len(identifying_cols) < 2:
            return issues
        
        # Check for duplicates based on identifying columns
        duplicates = df.duplicated(subset=identifying_cols, keep=False)
        
        if duplicates.any():
            # These might be technical replicates
            if 'replicate_id' not in df.columns:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Found {duplicates.sum()} potential duplicate samples. "
                        f"If these are technical replicates, add a replicate_id column. "
                        f"If biological replicates, ensure sample_id is unique."
                    ),
                    field=",".join(identifying_cols),
                    affected_records=int(duplicates.sum())
                ))
        
        return issues
    
    def _check_missing_data_patterns(
        self,
        df: pd.DataFrame
    ) -> List[ValidationIssue]:
        """Detect systematic missing data patterns."""
        issues = []
        
        # Check overall missingness
        missing_pct = df.isna().mean() * 100
        high_missing = missing_pct[missing_pct > 30]
        
        if not high_missing.empty:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=(
                    f"{len(high_missing)} columns have >30% missing data: "
                    f"{list(high_missing.index[:5])}. Consider if these are "
                    f"necessary or if missing data is systematic."
                ),
                field=",".join(high_missing.index[:5]),
                affected_records=0
            ))
        
        # Check if missing data correlates with batches
        if 'batch_id' in df.columns and len(high_missing) > 0:
            for col in high_missing.index[:3]:  # Check top 3
                missing_by_batch = df.groupby('batch_id')[col].apply(
                    lambda x: x.isna().mean()
                )
                
                if missing_by_batch.std() > 0.2:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Missing data in {col} varies significantly across batches. "
                            f"This suggests systematic measurement failure in some batches."
                        ),
                        field=col,
                        affected_records=0
                    ))
        
        return issues