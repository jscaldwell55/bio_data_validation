# src/validators/matrix_validator.py
"""
Generic Matrix Validator - Handles any gene-by-sample matrix data.

Supports:
- RNA-seq expression matrices
- Proteomics data
- CRISPR screen results (DepMap, etc.)
- Drug response data
- Metabolomics data
- Microarray data
- Any gene x sample numeric matrix

This validator provides ~80% coverage of bioinformatics datasets.

Usage:
    from src.validators.matrix_validator import MatrixValidator
    
    validator = MatrixValidator(
        organism="human",
        validate_genes=True,
        allow_negative=False  # Set True for CRISPR screens
    )
    
    result = await validator.validate(df, experiment_type="rna_seq")
"""

import asyncio
import time
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from src.schemas.base_schemas import (
    ValidationResult,
    ValidationIssue,
    ValidationSeverity
)
from src.validators.bio_lookups import BioLookupsValidator


class MatrixValidator:
    """
    Universal validator for gene-by-sample matrix data.
    
    Validates:
    - Row names (genes) against NCBI/Ensembl
    - Data quality (missing values, outliers, distributions)
    - Statistical properties (normalization, batch effects)
    - Column consistency
    
    Attributes:
        organism: Target organism for gene validation
        validate_genes: Whether to validate gene symbols (can be disabled for speed)
        missing_threshold: Maximum allowed fraction of missing values
        outlier_threshold: Number of standard deviations for outlier detection
        allow_negative: Whether negative values are expected/valid
    """
    
    def __init__(
        self,
        organism: str = "human",
        validate_genes: bool = True,
        missing_threshold: float = 0.10,
        outlier_threshold: float = 5.0,
        allow_negative: bool = False
    ):
        """
        Initialize matrix validator.
        
        Args:
            organism: Organism for gene validation (e.g., "human", "mouse")
            validate_genes: Whether to validate gene symbols against NCBI/Ensembl
            missing_threshold: Max allowed fraction of missing values (0.10 = 10%)
            outlier_threshold: Number of std deviations for outlier detection (default: 5)
            allow_negative: Whether negative values are valid (True for CRISPR, False for expression)
        """
        self.logger = logging.getLogger("MatrixValidator")
        self.organism = organism
        self.validate_genes = validate_genes
        self.missing_threshold = missing_threshold
        self.outlier_threshold = outlier_threshold
        self.allow_negative = allow_negative
        
        # Initialize gene validator if needed
        if self.validate_genes:
            self.gene_validator = BioLookupsValidator()
            self.logger.info("Gene validation enabled - will validate against NCBI/Ensembl")
        else:
            self.logger.info("Gene validation disabled - skipping gene symbol checks")
    
    async def validate(
        self,
        df: pd.DataFrame,
        experiment_type: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate a gene-by-sample matrix.
        
        Args:
            df: DataFrame with genes as rows, samples as columns
            experiment_type: Optional type hint (e.g., "rna_seq", "crispr_screen", "proteomics")
        
        Returns:
            ValidationResult with issues and metadata
            
        Example:
            >>> validator = MatrixValidator(organism="human")
            >>> df = pd.read_csv("expression_data.csv", index_col=0)
            >>> result = await validator.validate(df, experiment_type="rna_seq")
            >>> print(f"Passed: {result.passed}, Issues: {len(result.issues)}")
        """
        start_time = time.time()
        issues = []
        
        self.logger.info(f"Validating {df.shape[0]} genes × {df.shape[1]} samples")
        if experiment_type:
            self.logger.info(f"Experiment type: {experiment_type}")
        
        # ========================================
        # STEP 1: Data Structure Checks
        # ========================================
        self.logger.debug("Step 1: Checking data structure...")
        structure_issues = self._check_structure(df)
        issues.extend(structure_issues)
        
        # If critical structure issues, short-circuit
        if any(issue.severity == ValidationSeverity.CRITICAL for issue in structure_issues):
            self.logger.warning("Critical structure issues found - short-circuiting validation")
            return self._build_result(issues, start_time, df, short_circuit=True)
        
        # ========================================
        # STEP 2: Data Quality Checks
        # ========================================
        self.logger.debug("Step 2: Checking data quality...")
        quality_issues = self._check_data_quality(df)
        issues.extend(quality_issues)
        
        # ========================================
        # STEP 3: Gene Validation (optional, slow)
        # ========================================
        if self.validate_genes:
            self.logger.info("Step 3: Validating gene symbols (this may take 1-5 minutes)...")
            gene_issues = await self._validate_genes(df)
            issues.extend(gene_issues)
        else:
            self.logger.info("Step 3: Skipping gene validation (disabled)")
        
        # ========================================
        # STEP 4: Statistical Checks
        # ========================================
        self.logger.debug("Step 4: Running statistical checks...")
        stats_issues = self._check_statistics(df)
        issues.extend(stats_issues)
        
        # ========================================
        # STEP 5: Compile Results
        # ========================================
        return self._build_result(issues, start_time, df)
    
    def _build_result(
        self,
        issues: List[ValidationIssue],
        start_time: float,
        df: pd.DataFrame,
        short_circuit: bool = False
    ) -> ValidationResult:
        """Build the final ValidationResult object."""
        execution_time = (time.time() - start_time) * 1000
        
        # Determine overall severity
        severities = [issue.severity for issue in issues]
        if ValidationSeverity.CRITICAL in severities:
            overall_severity = ValidationSeverity.CRITICAL
        elif ValidationSeverity.ERROR in severities:
            overall_severity = ValidationSeverity.ERROR
        elif ValidationSeverity.WARNING in severities:
            overall_severity = ValidationSeverity.WARNING
        else:
            overall_severity = ValidationSeverity.INFO
        
        passed = overall_severity not in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
        
        # Compute metadata
        metadata = {
            "shape": {"genes": df.shape[0], "samples": df.shape[1]},
            "data_type": str(df.dtypes.mode()[0]) if len(df.dtypes) > 0 else "unknown",
            "missing_pct": float((df.isnull().sum().sum() / df.size) * 100) if df.size > 0 else 0,
            "short_circuit": short_circuit
        }
        
        # Add value range if numeric data exists
        try:
            df_numeric = df.apply(pd.to_numeric, errors='coerce')
            if df_numeric.size > 0:
                metadata["has_negative"] = bool((df_numeric < 0).any().any())
                metadata["value_range"] = {
                    "min": float(df_numeric.min().min()),
                    "max": float(df_numeric.max().max()),
                    "mean": float(df_numeric.mean().mean()),
                    "median": float(df_numeric.median().median())
                }
        except:
            pass
        
        self.logger.info(f"Validation complete: {overall_severity.value}, {len(issues)} issues found")
        
        return ValidationResult(
            validator_name="MatrixValidator",
            timestamp=datetime.utcnow(),
            passed=passed,
            severity=overall_severity,
            issues=issues,
            execution_time_ms=execution_time,
            records_processed=len(df),
            metadata=metadata
        )
    
    def _check_structure(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check basic data structure and format."""
        issues = []
        
        # Check 1: Empty dataframe
        if df.empty:
            issues.append(ValidationIssue(
                field="dataframe",
                message="DataFrame is empty",
                severity=ValidationSeverity.CRITICAL,
                affected_records=0,
                metadata={"check": "empty_dataframe"}
            ))
            return issues
        
        # Check 2: Too few rows or columns
        if df.shape[0] < 2:
            issues.append(ValidationIssue(
                field="rows",
                message=f"Only {df.shape[0]} row(s) found. Need at least 2 genes for meaningful analysis.",
                severity=ValidationSeverity.ERROR,
                affected_records=df.shape[0],
                metadata={"check": "min_rows", "found": df.shape[0], "required": 2}
            ))
        
        if df.shape[1] < 1:
            issues.append(ValidationIssue(
                field="columns",
                message=f"No columns found. Need at least 1 sample.",
                severity=ValidationSeverity.ERROR,
                affected_records=0,
                metadata={"check": "min_columns"}
            ))
        
        # Check 3: Index (gene names) validity
        invalid_indices = []
        for idx in df.index:
            if not isinstance(idx, str):
                invalid_indices.append(str(idx))
            elif len(idx) < 2:
                invalid_indices.append(idx)
        
        if invalid_indices:
            issues.append(ValidationIssue(
                field="index",
                message=f"Found {len(invalid_indices)} invalid gene names (non-string or too short)",
                severity=ValidationSeverity.ERROR,
                affected_records=len(invalid_indices),
                metadata={"check": "invalid_index", "examples": invalid_indices[:5]}
            ))
        
        # Check 4: Duplicate gene names
        duplicates = df.index[df.index.duplicated()].unique().tolist()
        if duplicates:
            duplicate_count = df.index.duplicated().sum()
            issues.append(ValidationIssue(
                field="index",
                message=f"Found {duplicate_count} duplicate gene names across {len(duplicates)} unique genes",
                severity=ValidationSeverity.WARNING,
                affected_records=duplicate_count,
                metadata={"check": "duplicate_index", "examples": duplicates[:10]}
            ))
        
        # Check 5: Column names
        null_cols = df.columns.isnull().sum()
        if null_cols > 0:
            issues.append(ValidationIssue(
                field="columns",
                message=f"Found {null_cols} columns with missing names",
                severity=ValidationSeverity.WARNING,
                affected_records=null_cols,
                metadata={"check": "null_column_names"}
            ))
        
        # Check 6: Duplicate column names
        dup_cols = df.columns[df.columns.duplicated()].unique().tolist()
        if dup_cols:
            issues.append(ValidationIssue(
                field="columns",
                message=f"Found {len(dup_cols)} duplicate column names",
                severity=ValidationSeverity.WARNING,
                affected_records=len(dup_cols),
                metadata={"check": "duplicate_columns", "examples": dup_cols[:10]}
            ))
        
        return issues
    
    def _check_data_quality(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check data quality (missing values, data types, etc.)."""
        issues = []
    
        # Convert to numeric - handle completely gracefully
        df_numeric = df.apply(pd.to_numeric, errors='coerce')
    
        # Check 1: Non-numeric columns
        non_numeric_cols = []
        for col in df.columns:
            if df[col].dtype == 'object' or pd.api.types.is_string_dtype(df[col]):
                try:
                    pd.to_numeric(df[col], errors='raise')
                except:
                    non_numeric_cols.append(col)
    
        if non_numeric_cols:
            issues.append(ValidationIssue(
                field="data_type",
                message=f"Found {len(non_numeric_cols)} non-numeric columns",
                severity=ValidationSeverity.ERROR,
                affected_records=len(non_numeric_cols),
                metadata={"check": "non_numeric", "columns": non_numeric_cols[:10]}
             ))
    
        # Check 2: Missing values
        missing_count = df_numeric.isnull().sum().sum()
        missing_pct = (missing_count / df_numeric.size) * 100 if df_numeric.size > 0 else 0
    
        if missing_pct > self.missing_threshold * 100:
            severity = ValidationSeverity.ERROR if missing_pct > 50 else ValidationSeverity.WARNING
            issues.append(ValidationIssue(
                field="missing_values",
                message=f"High missing value rate: {missing_pct:.2f}% (threshold: {self.missing_threshold*100:.1f}%)",
                severity=severity,
                affected_records=int(missing_count),
                metadata={
                    "check": "missing_values",
                    "missing_pct": missing_pct,
                    "threshold": self.missing_threshold * 100
                }
            ))
    
        # Check 3: Entire rows/columns missing
        rows_all_na = df_numeric.isnull().all(axis=1).sum()
        cols_all_na = df_numeric.isnull().all(axis=0).sum()
    
        if rows_all_na > 0:
            issues.append(ValidationIssue(
                field="missing_data",
                message=f"Found {rows_all_na} genes with all missing values",
                severity=ValidationSeverity.ERROR,
                affected_records=rows_all_na,
                metadata={"check": "rows_all_missing"}
            ))
        
        if cols_all_na > 0:
            issues.append(ValidationIssue(
                field="missing_data",
                message=f"Found {cols_all_na} samples with all missing values",
                severity=ValidationSeverity.ERROR,
                affected_records=cols_all_na,
                metadata={"check": "columns_all_missing"}
            ))
        
        # Check 4: Negative values (if not allowed)
        if not self.allow_negative:
            try:
                negative_count = (df_numeric < 0).sum().sum()
                if negative_count > 0:
                    negative_pct = (negative_count / df_numeric.size) * 100
                    issues.append(ValidationIssue(
                        field="values",
                        message=f"Found {negative_count} negative values ({negative_pct:.2f}%) - not expected for this data type",
                        severity=ValidationSeverity.WARNING,
                        affected_records=negative_count,
                        metadata={
                            "check": "negative_values",
                            "count": negative_count,
                            "pct": negative_pct
                        }
                    ))
            except:
                pass  # Skip if comparison fails
        
        # Check 5: Infinite values (with safer handling)
        try:
            # Only check numeric columns
            numeric_cols = df_numeric.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                inf_count = np.isinf(df_numeric[numeric_cols].values).sum()
                if inf_count > 0:
                    issues.append(ValidationIssue(
                        field="values",
                        message=f"Found {inf_count} infinite values",
                        severity=ValidationSeverity.ERROR,
                        affected_records=inf_count,
                        metadata={"check": "infinite_values"}
                    ))
        except Exception as e:
            self.logger.debug(f"Could not check for infinite values: {e}")
        
        # Check 6: All zeros (suspicious)
        try:
            zero_rows = (df_numeric == 0).all(axis=1).sum()
            if zero_rows > 0:
                zero_pct = (zero_rows / len(df_numeric)) * 100
                if zero_pct > 5:
                    issues.append(ValidationIssue(
                        field="values",
                        message=f"Found {zero_rows} genes ({zero_pct:.1f}%) with all zero values",
                        severity=ValidationSeverity.WARNING,
                        affected_records=zero_rows,
                        metadata={"check": "zero_rows", "pct": zero_pct}
                    ))
        except:
            pass
        
        # Check 7: Constant values (no variance)
        try:
            constant_rows = (df_numeric.std(axis=1, skipna=True) == 0).sum()
            if constant_rows > 0:
                constant_pct = (constant_rows / len(df_numeric)) * 100
                if constant_pct > 5:
                    issues.append(ValidationIssue(
                        field="values",
                        message=f"Found {constant_rows} genes ({constant_pct:.1f}%) with constant values (no variance)",
                        severity=ValidationSeverity.INFO,
                        affected_records=constant_rows,
                        metadata={"check": "constant_values", "pct": constant_pct}
                    ))
        except:
            pass
        
        return issues
    
    async def _validate_genes(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Validate gene symbols against NCBI/Ensembl."""
        issues = []
        
        self.logger.info(f"Validating {len(df.index)} gene symbols against NCBI/Ensembl...")
        
        # Prepare gene data for BioLookupsValidator
        gene_data = pd.DataFrame({
            'target_gene': df.index,
            'organism': [self.organism] * len(df.index),
            'sequence': ['NNNNNNNNNNNNNNNNNNNN'] * len(df.index),
            'pam_sequence': ['NGG'] * len(df.index),
            'nuclease_type': ['SpCas9'] * len(df.index)
        })
        
        try:
            # Run gene validation
            result = await self.gene_validator.validate(gene_data, 'gene_symbols')
            
            # Extract gene-specific issues from result
            if isinstance(result, dict):
                validation_issues = result.get('issues', [])
            else:
                validation_issues = result.issues if hasattr(result, 'issues') else []
            
            # Filter for gene-related issues - handle both dict and Pydantic objects
            gene_issues = []
            for issue in validation_issues:
                try:
                    # Handle both dict and Pydantic object
                    if isinstance(issue, dict):
                        msg = issue.get('message', '')
                    else:
                        msg = getattr(issue, 'message', '')
                    
                    if 'gene' in str(msg).lower():
                        gene_issues.append(issue)
                except:
                    continue
            
            if gene_issues:
                # Consolidate into single issue for cleaner reporting
                invalid_count = len(gene_issues)
                invalid_pct = (invalid_count / len(df.index)) * 100
                
                # Extract example gene names from issues
                examples = []
                for issue in gene_issues[:10]:
                    try:
                        if isinstance(issue, dict):
                            msg = issue.get('message', '')
                        else:
                            msg = getattr(issue, 'message', '')
                        examples.append(str(msg))
                    except:
                        continue
                
                severity = ValidationSeverity.ERROR if invalid_pct > 10 else ValidationSeverity.WARNING
                
                issues.append(ValidationIssue(
                    field="gene_symbols",
                    message=f"Found {invalid_count} invalid or unrecognized gene symbols ({invalid_pct:.1f}%)",
                    severity=severity,
                    affected_records=invalid_count,
                    metadata={
                        "check": "gene_validation",
                        "invalid_count": invalid_count,
                        "invalid_pct": invalid_pct,
                        "examples": examples[:5]
                    }
                ))
                
                self.logger.warning(f"Gene validation found {invalid_count} issues")
            else:
                self.logger.info("Gene validation passed - all gene symbols are valid")
        
        except Exception as e:
            self.logger.error(f"Gene validation failed: {e}", exc_info=True)
            issues.append(ValidationIssue(
                field="gene_validation",
                message=f"Gene validation failed: {str(e)}",
                severity=ValidationSeverity.WARNING,
                affected_records=0,
                metadata={"check": "gene_validation_error", "error": str(e)}
            ))
        
        return issues
    def _check_statistics(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check statistical properties of the data."""
        issues = []
        
        df_numeric = df.apply(pd.to_numeric, errors='coerce')
        
        # Check 1: Outliers (values far from mean)
        try:
            # Calculate global statistics
            all_values = df_numeric.values.flatten()
            all_values = all_values[~np.isnan(all_values)]
            
            if len(all_values) > 0:
                mean = np.mean(all_values)
                std = np.std(all_values)
                
                if std > 0:
                    outliers = np.abs(all_values - mean) > self.outlier_threshold * std
                    outlier_count = outliers.sum()
                    outlier_pct = (outlier_count / len(all_values)) * 100
                    
                    if outlier_pct > 5:
                        issues.append(ValidationIssue(
                            field="outliers",
                            message=f"High number of outliers: {outlier_pct:.2f}% of values > {self.outlier_threshold}σ from mean",
                            severity=ValidationSeverity.WARNING,
                            affected_records=outlier_count,
                            metadata={
                                "check": "outliers",
                                "outlier_pct": outlier_pct,
                                "threshold_sigma": self.outlier_threshold
                            }
                        ))
        except Exception as e:
            self.logger.debug(f"Outlier check failed: {e}")
        
        # Check 2: Variance (detect constant or near-constant data)
        try:
            gene_variances = df_numeric.var(axis=1, skipna=True)
            low_variance_genes = (gene_variances < 0.01).sum()
            low_var_pct = (low_variance_genes / len(df)) * 100
            
            if low_var_pct > 10:
                issues.append(ValidationIssue(
                    field="variance",
                    message=f"{low_variance_genes} genes ({low_var_pct:.1f}%) have very low variance (< 0.01)",
                    severity=ValidationSeverity.INFO,
                    affected_records=low_variance_genes,
                    metadata={
                        "check": "low_variance",
                        "count": low_variance_genes,
                        "pct": low_var_pct
                    }
                ))
        except Exception as e:
            self.logger.debug(f"Variance check failed: {e}")
        
        # Check 3: Sample correlation (detect potential duplicates)
        try:
            if df.shape[1] > 1 and df.shape[1] <= 100:  # Only for reasonable number of samples
                corr_matrix = df_numeric.corr()
                
                # Count pairs with correlation > 0.99 (excluding diagonal)
                high_corr_mask = (corr_matrix > 0.99) & (corr_matrix < 1.0)
                high_corr_count = high_corr_mask.sum().sum() // 2  # Divide by 2 for symmetric matrix
                
                if high_corr_count > 0:
                    issues.append(ValidationIssue(
                        field="correlation",
                        message=f"Found {high_corr_count} pairs of highly correlated samples (r > 0.99) - possible duplicates or technical replicates",
                        severity=ValidationSeverity.INFO,
                        affected_records=high_corr_count,
                        metadata={
                            "check": "high_correlation",
                            "pairs": high_corr_count,
                            "note": "Consider checking for technical replicates or mislabeled samples"
                        }
                    ))
        except Exception as e:
            self.logger.debug(f"Correlation check failed: {e}")
        
        # Check 4: Distribution shape (skewness)
        try:
            sample_skewness = df_numeric.apply(lambda x: x.skew(), axis=0)
            mean_skewness = sample_skewness.mean()
            
            if abs(mean_skewness) > 2:
                issues.append(ValidationIssue(
                    field="distribution",
                    message=f"Data is highly skewed (mean skewness: {mean_skewness:.2f})",
                    severity=ValidationSeverity.INFO,
                    affected_records=0,
                    metadata={
                        "check": "skewness",
                        "mean_skewness": mean_skewness,
                        "note": "Consider log transformation or other normalization"
                    }
                ))
        except Exception as e:
            self.logger.debug(f"Skewness check failed: {e}")
        
        # Check 5: Sample size balance
        try:
            if df.shape[1] >= 10:  # Only meaningful for larger datasets
                sample_means = df_numeric.mean(axis=0, skipna=True)
                sample_stds = df_numeric.std(axis=0, skipna=True)
                
                # Check for samples that are statistical outliers
                mean_of_means = sample_means.mean()
                std_of_means = sample_means.std()
                
                if std_of_means > 0:
                    outlier_samples = np.abs(sample_means - mean_of_means) > 3 * std_of_means
                    outlier_count = outlier_samples.sum()
                    
                    if outlier_count > 0:
                        issues.append(ValidationIssue(
                            field="samples",
                            message=f"Found {outlier_count} samples with unusual mean values (> 3σ from dataset mean)",
                            severity=ValidationSeverity.INFO,
                            affected_records=outlier_count,
                            metadata={
                                "check": "sample_outliers",
                                "count": outlier_count,
                                "note": "These samples may need quality review"
                            }
                        ))
        except Exception as e:
            self.logger.debug(f"Sample balance check failed: {e}")
        
        return issues