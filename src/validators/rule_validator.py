# src/validators/rule_validator.py
import time
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import logging

from src.schemas.base_schemas import (
    ConfigurableComponent,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity
)

logger = logging.getLogger(__name__)

class RuleValidator(ConfigurableComponent):
    """
    Vectorized rule-based validator that combines consistency, duplicate detection,
    and bias detection using pandas operations.
    """
    
    def __init__(
        self,
        config: Optional[Union[str, Path, Dict[str, Any]]] = None,
        **kwargs
    ):
        """
        Initialize with validation rules from flexible configuration.

        Args:
            config: Can be:
                - str/Path: Path to validation rules YAML file
                - dict: Configuration dictionary (for testing)
                - None: Use default configuration
            **kwargs: Additional config overrides
        """
        # Initialize parent with base config
        super().__init__(config, **kwargs)

        # Extract rules from config
        self.rules = self.config.get('rules', {})
        logger.info(f"Loaded {len(self.rules)} validation rules")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default rules configuration with sensible defaults for biological data"""
        return {
            'rules': {
                'consistency': {
                    'required_columns': [],
                    'column_types': {},
                    'value_ranges': {
                        'gc_content': {'min': 0.0, 'max': 1.0},
                        'efficiency_score': {'min': 0.0, 'max': 1.0},
                        'on_target_score': {'min': 0.0, 'max': 1.0},
                        'off_target_score': {'min': 0.0, 'max': 1.0}
                    },
                    'cross_column': [
                        {'column1': 'end_position', 'operator': '>', 'column2': 'start_position'}
                    ]
                },
                'duplicates': {
                    'check_duplicate_rows': True,
                    'unique_columns': ['guide_id'],
                    'sequence_similarity_threshold': 0.95,
                    'sequence_columns': ['sequence']
                },
                'bias': {
                    'target_column': 'efficiency_score',
                    'imbalance_threshold': 0.3,
                    'missing_value_threshold': 0.1,
                    'check_distribution_bias': []
                },
                'custom': []
            }
        }
    
    def validate(
        self,
        df: pd.DataFrame,
        dataset_metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Perform vectorized rule-based validation on DataFrame.
        
        Args:
            df: DataFrame to validate
            dataset_metadata: Optional metadata about the dataset
            
        Returns:
            ValidationResult with all detected issues
        """
        start_time = time.time()
        issues: List[ValidationIssue] = []
        
        try:
            # Run consistency checks
            issues.extend(self._check_consistency(df))
            
            # Run duplicate detection
            issues.extend(self._check_duplicates(df))
            
            # Run bias detection
            issues.extend(self._check_bias(df, dataset_metadata))
            
            # Run custom rules
            issues.extend(self._apply_custom_rules(df))
        
        except Exception as e:
            logger.exception(f"Rule validation error: {str(e)}")
            issues.append(ValidationIssue(
                field="system",
                message=f"Rule validation system error: {str(e)}",
                severity=ValidationSeverity.CRITICAL
            ))
        
        execution_time = (time.time() - start_time) * 1000
        
        # Determine pass/fail and severity
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
            validator_name="RuleValidator",
            passed=not has_errors,
            severity=severity,
            issues=issues,
            execution_time_ms=execution_time,
            records_processed=len(df),
            metadata={"total_rules_applied": len(self.rules)}
        )
    
    def _check_consistency(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Vectorized consistency checks"""
        issues = []
        
        consistency_rules = self.rules.get('consistency', {})
        
        # Check for required columns
        required_cols = consistency_rules.get('required_columns', [])
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            issues.append(ValidationIssue(
                field="columns",
                message=f"Missing required columns: {missing_cols}",
                severity=ValidationSeverity.ERROR,
                rule_id="CONS_001"
            ))
        
        # Check data types (vectorized)
        expected_types = consistency_rules.get('column_types', {})
        for col, expected_type in expected_types.items():
            if col in df.columns:
                actual_type = df[col].dtype
                if not self._is_compatible_type(actual_type, expected_type):
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"Expected type {expected_type}, got {actual_type}",
                        severity=ValidationSeverity.ERROR,
                        rule_id="CONS_002"
                    ))
        
        # Check value ranges (vectorized)
        range_rules = consistency_rules.get('value_ranges', {})
        for col, range_spec in range_rules.items():
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                min_val = range_spec.get('min')
                max_val = range_spec.get('max')
                
                if min_val is not None:
                    violations = df[df[col] < min_val]
                    if not violations.empty:
                        issues.append(ValidationIssue(
                            field=col,
                            message=f"{len(violations)} values outside valid range (below minimum {min_val})",
                            severity=ValidationSeverity.ERROR,
                            rule_id="CONS_003",
                            metadata={"violation_count": len(violations)}
                        ))

                if max_val is not None:
                    violations = df[df[col] > max_val]
                    if not violations.empty:
                        issues.append(ValidationIssue(
                            field=col,
                            message=f"{len(violations)} values outside valid range (above maximum {max_val})",
                            severity=ValidationSeverity.ERROR,
                            rule_id="CONS_004",
                            metadata={"violation_count": len(violations)}
                        ))
        
        # Check cross-column consistency
        cross_col_rules = consistency_rules.get('cross_column', [])
        for rule in cross_col_rules:
            col1, operator, col2 = rule['column1'], rule['operator'], rule['column2']
            if col1 in df.columns and col2 in df.columns:
                if operator == '>':
                    violations = df[df[col1] <= df[col2]]
                elif operator == '<':
                    violations = df[df[col1] >= df[col2]]
                elif operator == '==':
                    violations = df[df[col1] != df[col2]]
                
                if not violations.empty:
                    issues.append(ValidationIssue(
                        field=f"{col1},{col2}",
                        message=f"Cross-column rule violated: {col1} {operator} {col2}",
                        severity=ValidationSeverity.ERROR,
                        rule_id="CONS_005",
                        metadata={"violation_count": len(violations)}
                    ))
        
        return issues
    
    def _check_duplicates(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Vectorized duplicate detection"""
        issues = []
        
        duplicate_rules = self.rules.get('duplicates', {})
        
        # Check for duplicate rows (vectorized)
        if duplicate_rules.get('check_duplicate_rows', True):
            dup_mask = df.duplicated(keep=False)
            dup_count = dup_mask.sum()
            if dup_count > 0:
                issues.append(ValidationIssue(
                    field="rows",
                    message=f"Found {dup_count} duplicate rows",
                    severity=ValidationSeverity.WARNING,
                    rule_id="DUP_001",
                    metadata={"duplicate_count": int(dup_count)}
                ))
        
        # Check for duplicate values in unique columns (vectorized)
        unique_columns = duplicate_rules.get('unique_columns', [])
        for col in unique_columns:
            if col in df.columns:
                dup_mask = df[col].duplicated(keep=False)
                dup_count = dup_mask.sum()
                if dup_count > 0:
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"Column should contain unique values, found {dup_count} duplicates",
                        severity=ValidationSeverity.ERROR,
                        rule_id="DUP_002",
                        metadata={"duplicate_count": int(dup_count)}
                    ))
        
        # FIXED: Check for near-duplicate sequences (sequence similarity)
        similarity_threshold = duplicate_rules.get('sequence_similarity_threshold', 0.95)
        sequence_columns = duplicate_rules.get('sequence_columns', [])
        
        for col in sequence_columns:
            if col in df.columns:
                # Check for exact duplicate sequences
                dup_seq_mask = df[col].duplicated(keep=False)
                exact_dup_count = dup_seq_mask.sum()
                
                if exact_dup_count > 0:
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"Found {exact_dup_count} duplicate sequences",
                        severity=ValidationSeverity.WARNING,
                        rule_id="DUP_003",
                        metadata={"duplicate_count": int(exact_dup_count)}
                    ))
                
                # For near-duplicate detection (more sophisticated)
                # This is a simplified version - production would use edit distance
                near_dups = self._find_near_duplicate_sequences(
                    df[col].tolist(), 
                    similarity_threshold
                )
                if near_dups > 0:
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"Found {near_dups} near-duplicate sequence pairs (>{similarity_threshold*100}% similar)",
                        severity=ValidationSeverity.WARNING,
                        rule_id="DUP_004",
                        metadata={"near_duplicate_pairs": near_dups}
                    ))
        
        return issues
    
    def _check_bias(self, df: pd.DataFrame, metadata: Optional[Dict]) -> List[ValidationIssue]:
        """Vectorized bias detection"""
        issues = []
        
        bias_rules = self.rules.get('bias', {})
        
        # FIXED: Check class imbalance for ANY column type
        target_col = bias_rules.get('target_column')
        imbalance_threshold = bias_rules.get('imbalance_threshold', 0.3)
        
        if target_col and target_col in df.columns:
            # For categorical or binary targets
            if df[target_col].dtype in ['object', 'category', 'bool'] or df[target_col].nunique() <= 10:
                value_counts = df[target_col].value_counts(normalize=True)
                min_proportion = value_counts.min()
                
                if min_proportion < imbalance_threshold:
                    issues.append(ValidationIssue(
                        field=target_col,
                        message=f"Class imbalance detected: minimum class proportion is {min_proportion:.2%}",
                        severity=ValidationSeverity.WARNING,
                        rule_id="BIAS_001",
                        metadata={
                            "class_distribution": {str(k): float(v) for k, v in value_counts.items()},
                            "min_proportion": float(min_proportion)
                        }
                    ))
            
            # FIXED: Also check continuous data by binning
            elif pd.api.types.is_numeric_dtype(df[target_col]):
                # For continuous data, bin into quartiles and check distribution
                try:
                    binned = pd.qcut(df[target_col], q=4, labels=False, duplicates='drop')
                    value_counts = binned.value_counts(normalize=True)
                    min_proportion = value_counts.min()
                    
                    if min_proportion < imbalance_threshold:
                        issues.append(ValidationIssue(
                            field=target_col,
                            message=f"Distribution imbalance detected: minimum quartile proportion is {min_proportion:.2%}",
                            severity=ValidationSeverity.WARNING,
                            rule_id="BIAS_001B",
                            metadata={
                                "quartile_distribution": {str(k): float(v) for k, v in value_counts.items()},
                                "min_proportion": float(min_proportion)
                            }
                        ))
                except Exception as e:
                    logger.debug(f"Could not bin continuous data for {target_col}: {e}")
        
        # FIXED: Check for missing value bias (vectorized)
        missing_threshold = bias_rules.get('missing_value_threshold', 0.1)
        missing_props = df.isnull().sum() / len(df)
        biased_cols = missing_props[missing_props > missing_threshold]
        
        if not biased_cols.empty:
            for col, prop in biased_cols.items():
                issues.append(ValidationIssue(
                    field=str(col),
                    message=f"High missing value rate: {prop:.2%}",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIAS_002",
                    metadata={"missing_proportion": float(prop)}
                ))
        
        # Check for statistical distribution bias
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        check_bias_cols = bias_rules.get('check_distribution_bias', [])
        
        for col in numeric_cols:
            if col in check_bias_cols:
                # Check skewness
                skewness = df[col].skew()
                if abs(skewness) > 2:
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"High skewness detected: {skewness:.2f}",
                        severity=ValidationSeverity.INFO,
                        rule_id="BIAS_003",
                        metadata={"skewness": float(skewness)}
                    ))
        
        return issues
    
    def _apply_custom_rules(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Apply custom user-defined rules"""
        issues = []
        
        custom_rules = self.rules.get('custom', [])
        
        for rule in custom_rules:
            rule_id = rule.get('id')
            rule_expr = rule.get('expression')
            message = rule.get('message')
            severity = ValidationSeverity(rule.get('severity', 'warning'))
            
            try:
                # Evaluate rule expression (uses pandas query syntax)
                violations = df.query(f"not ({rule_expr})")
                
                if not violations.empty:
                    issues.append(ValidationIssue(
                        field=rule.get('field', 'custom'),
                        message=f"{message} ({len(violations)} violations)",
                        severity=severity,
                        rule_id=rule_id,
                        metadata={"violation_count": len(violations)}
                    ))
            except Exception as e:
                logger.error(f"Error evaluating custom rule {rule_id}: {str(e)}")
        
        return issues
    
    @staticmethod
    def _is_compatible_type(actual_type, expected_type: str) -> bool:
        """Check if actual dtype is compatible with expected type"""
        type_map = {
            'int': pd.api.types.is_integer_dtype,
            'float': pd.api.types.is_float_dtype,
            'string': pd.api.types.is_string_dtype,
            'bool': pd.api.types.is_bool_dtype,
            'datetime': pd.api.types.is_datetime64_any_dtype,
        }
        
        check_func = type_map.get(expected_type.lower())
        return check_func(actual_type) if check_func else True
    
    @staticmethod
    def _find_near_duplicate_sequences(sequences: List[str], threshold: float) -> int:
        """
        Find near-duplicate sequences (simplified implementation)
        Returns count of near-duplicate pairs found
        """
        # FIXED: Simplified implementation that actually works
        # In production, use Levenshtein distance or similar
        near_dup_count = 0
        
        # Convert to set for faster comparison
        unique_seqs = list(set(sequences))
        
        # For small datasets, do pairwise comparison
        if len(unique_seqs) < 1000:
            for i in range(len(unique_seqs)):
                for j in range(i + 1, len(unique_seqs)):
                    seq1, seq2 = unique_seqs[i], unique_seqs[j]
                    
                    # Skip if lengths are too different
                    if abs(len(seq1) - len(seq2)) > max(len(seq1), len(seq2)) * (1 - threshold):
                        continue
                    
                    # Simple similarity: count matching characters at same positions
                    if len(seq1) == len(seq2):
                        matches = sum(c1 == c2 for c1, c2 in zip(seq1, seq2))
                        similarity = matches / len(seq1)
                        
                        if similarity >= threshold and similarity < 1.0:
                            near_dup_count += 1
        
        return near_dup_count