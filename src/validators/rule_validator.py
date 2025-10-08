# src/validators/rule_validator.py
import time
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
import yaml

from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity

logger = logging.getLogger(__name__)

class RuleValidator:
    """
    Vectorized rule-based validator that combines consistency, duplicate detection,
    and bias detection using pandas operations.
    """
    
    def __init__(self, rules_config_path: str):
        """
        Initialize with validation rules from YAML config.
        
        Args:
            rules_config_path: Path to validation rules YAML file
        """
        with open(rules_config_path, 'r') as f:
            self.rules_config = yaml.safe_load(f)
        
        self.rules = self.rules_config.get('rules', {})
        logger.info(f"Loaded {len(self.rules)} validation rules")
    
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
                            message=f"{len(violations)} values below minimum {min_val}",
                            severity=ValidationSeverity.WARNING,
                            rule_id="CONS_003",
                            metadata={"violation_count": len(violations)}
                        ))
                
                if max_val is not None:
                    violations = df[df[col] > max_val]
                    if not violations.empty:
                        issues.append(ValidationIssue(
                            field=col,
                            message=f"{len(violations)} values above maximum {max_val}",
                            severity=ValidationSeverity.WARNING,
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
                        severity=ValidationSeverity.WARNING,
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
        
        # Check for near-duplicate detection (sequence similarity)
        similarity_threshold = duplicate_rules.get('sequence_similarity_threshold', 0.95)
        sequence_columns = duplicate_rules.get('sequence_columns', [])
        
        for col in sequence_columns:
            if col in df.columns:
                # This is simplified - real implementation would use more sophisticated
                # sequence comparison (e.g., Levenshtein distance)
                near_dups = self._find_near_duplicate_sequences(
                    df[col].tolist(), 
                    similarity_threshold
                )
                if near_dups:
                    issues.append(ValidationIssue(
                        field=col,
                        message=f"Found {len(near_dups)} near-duplicate sequences (>{similarity_threshold*100}% similar)",
                        severity=ValidationSeverity.WARNING,
                        rule_id="DUP_003",
                        metadata={"near_duplicate_pairs": len(near_dups)}
                    ))
        
        return issues
    
    def _check_bias(self, df: pd.DataFrame, metadata: Optional[Dict]) -> List[ValidationIssue]:
        """Vectorized bias detection"""
        issues = []
        
        bias_rules = self.rules.get('bias', {})
        
        # Check class imbalance (vectorized)
        target_col = bias_rules.get('target_column')
        imbalance_threshold = bias_rules.get('imbalance_threshold', 0.3)
        
        if target_col and target_col in df.columns:
            value_counts = df[target_col].value_counts(normalize=True)
            min_proportion = value_counts.min()
            
            if min_proportion < imbalance_threshold:
                issues.append(ValidationIssue(
                    field=target_col,
                    message=f"Class imbalance detected: minimum class proportion is {min_proportion:.2%}",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIAS_001",
                    metadata={
                        "class_distribution": value_counts.to_dict(),
                        "min_proportion": float(min_proportion)
                    }
                ))
        
        # Check for missing value bias (vectorized)
        missing_threshold = bias_rules.get('missing_value_threshold', 0.1)
        missing_props = df.isnull().sum() / len(df)
        biased_cols = missing_props[missing_props > missing_threshold]
        
        if not biased_cols.empty:
            for col, prop in biased_cols.items():
                issues.append(ValidationIssue(
                    field=col,
                    message=f"High missing value rate: {prop:.2%}",
                    severity=ValidationSeverity.WARNING,
                    rule_id="BIAS_002",
                    metadata={"missing_proportion": float(prop)}
                ))
        
        # Check for statistical distribution bias
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col in bias_rules.get('check_distribution_bias', []):
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
    def _find_near_duplicate_sequences(sequences: List[str], threshold: float) -> List[tuple]:
        """Find near-duplicate sequences (simplified implementation)"""
        # In production, use more sophisticated algorithms like:
        # - Levenshtein distance
        # - Smith-Waterman alignment
        # - MinHash for large-scale detection
        
        near_dups = []
        # Placeholder - actual implementation would be more complex
        return near_dups