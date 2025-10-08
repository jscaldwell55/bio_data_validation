# src/validators/schema_validator.py
import time
from typing import Any, List, Dict, Union
from pydantic import BaseModel, Field, validator, ValidationError
from Bio import SeqIO
from io import StringIO
import pandas as pd
import logging

from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity
from src.schemas.biological_schemas import SequenceRecord, GuideRNARecord

logger = logging.getLogger(__name__)

def validate_schema(
    dataset: Any,
    schema_type: str,
    strict: bool = True
) -> ValidationResult:
    """
    Validate dataset against predefined schemas.
    
    Args:
        dataset: Data to validate (dict, list, DataFrame, or string)
        schema_type: Type of schema ('fasta', 'guide_rna', 'json', etc.)
        strict: Whether to fail on first error or collect all errors
        
    Returns:
        ValidationResult with all validation issues
    """
    start_time = time.time()
    issues: List[ValidationIssue] = []
    records_processed = 0
    
    try:
        if schema_type == 'fasta':
            issues, records_processed = _validate_fasta(dataset, strict)
        elif schema_type == 'guide_rna':
            issues, records_processed = _validate_guide_rna(dataset, strict)
        elif schema_type == 'json':
            issues, records_processed = _validate_json(dataset, strict)
        elif schema_type == 'tabular':
            issues, records_processed = _validate_tabular(dataset, strict)
        else:
            issues.append(ValidationIssue(
                field="schema_type",
                message=f"Unsupported schema type: {schema_type}",
                severity=ValidationSeverity.ERROR
            ))
    
    except Exception as e:
        logger.exception(f"Schema validation error: {str(e)}")
        issues.append(ValidationIssue(
            field="system",
            message=f"Schema validation system error: {str(e)}",
            severity=ValidationSeverity.CRITICAL
        ))
    
    execution_time = (time.time() - start_time) * 1000
    
    # Determine if validation passed
    has_errors = any(i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] 
                     for i in issues)
    
    # Determine overall severity
    if any(i.severity == ValidationSeverity.CRITICAL for i in issues):
        severity = ValidationSeverity.CRITICAL
    elif any(i.severity == ValidationSeverity.ERROR for i in issues):
        severity = ValidationSeverity.ERROR
    elif any(i.severity == ValidationSeverity.WARNING for i in issues):
        severity = ValidationSeverity.WARNING
    else:
        severity = ValidationSeverity.INFO
    
    return ValidationResult(
        validator_name="SchemaValidator",
        passed=not has_errors,
        severity=severity,
        issues=issues,
        execution_time_ms=execution_time,
        records_processed=records_processed,
        metadata={"schema_type": schema_type, "strict_mode": strict}
    )


def _validate_fasta(data: str, strict: bool) -> tuple[List[ValidationIssue], int]:
    """Validate FASTA format using BioPython"""
    issues = []
    records_processed = 0
    
    try:
        records = list(SeqIO.parse(StringIO(data), "fasta"))
        
        if not records:
            issues.append(ValidationIssue(
                field="records",
                message="No valid FASTA records found",
                severity=ValidationSeverity.ERROR
            ))
            return issues, 0
        
        for idx, record in enumerate(records):
            records_processed += 1
            
            # Validate record ID
            if not record.id:
                issues.append(ValidationIssue(
                    field=f"record_{idx}.id",
                    message="Missing sequence ID",
                    severity=ValidationSeverity.ERROR
                ))
                if strict:
                    break
            
            # Validate sequence
            if len(record.seq) == 0:
                issues.append(ValidationIssue(
                    field=f"record_{idx}.sequence",
                    message="Empty sequence",
                    severity=ValidationSeverity.ERROR
                ))
                if strict:
                    break
            
            # Check for high ambiguous content
            ambiguous_count = str(record.seq).upper().count('N')
            if len(record.seq) > 0 and ambiguous_count / len(record.seq) > 0.1:
                issues.append(ValidationIssue(
                    field=f"record_{idx}.sequence",
                    message=f"High ambiguous base content: {ambiguous_count}/{len(record.seq)}",
                    severity=ValidationSeverity.WARNING
                ))
    
    except Exception as e:
        issues.append(ValidationIssue(
            field="fasta_parse",
            message=f"FASTA parsing error: {str(e)}",
            severity=ValidationSeverity.ERROR
        ))
    
    return issues, records_processed


def _validate_guide_rna(data: Union[Dict, List[Dict]], strict: bool) -> tuple[List[ValidationIssue], int]:
    """Validate guide RNA records using Pydantic"""
    issues = []
    records_processed = 0
    
    # Convert single dict to list
    records = [data] if isinstance(data, dict) else data
    
    for idx, record in enumerate(records):
        try:
            records_processed += 1
            guide = GuideRNARecord(**record)
            
            # Additional domain-specific checks
            if len(guide.sequence) < 18:
                issues.append(ValidationIssue(
                    field=f"record_{idx}.sequence",
                    message=f"Guide RNA too short: {len(guide.sequence)}bp (minimum 18bp)",
                    severity=ValidationSeverity.ERROR
                ))
                if strict:
                    break
            
            if len(guide.sequence) > 24:
                issues.append(ValidationIssue(
                    field=f"record_{idx}.sequence",
                    message=f"Guide RNA too long: {len(guide.sequence)}bp (maximum 24bp)",
                    severity=ValidationSeverity.WARNING
                ))
        
        except ValidationError as e:
            for error in e.errors():
                issues.append(ValidationIssue(
                    field=f"record_{idx}.{'.'.join(str(loc) for loc in error['loc'])}",
                    message=error['msg'],
                    severity=ValidationSeverity.ERROR
                ))
                if strict:
                    break
            if strict:
                break
    
    return issues, records_processed


def _validate_json(data: Union[Dict, List], strict: bool) -> tuple[List[ValidationIssue], int]:
    """Validate JSON data structure"""
    issues = []
    records_processed = 1 if isinstance(data, dict) else len(data)
    
    # Basic JSON validation - structure is already validated by parser
    # Add custom validation logic here if needed
    
    return issues, records_processed


def _validate_tabular(data: pd.DataFrame, strict: bool) -> tuple[List[ValidationIssue], int]:
    """Validate tabular data using pandas"""
    issues = []
    records_processed = len(data)
    
    # Check for empty DataFrame
    if data.empty:
        issues.append(ValidationIssue(
            field="dataframe",
            message="Empty DataFrame provided",
            severity=ValidationSeverity.ERROR
        ))
        return issues, 0
    
    # Check for duplicate column names
    if data.columns.duplicated().any():
        dup_cols = data.columns[data.columns.duplicated()].tolist()
        issues.append(ValidationIssue(
            field="columns",
            message=f"Duplicate column names found: {dup_cols}",
            severity=ValidationSeverity.ERROR
        ))
    
    # Check for completely null columns
    null_cols = data.columns[data.isnull().all()].tolist()
    if null_cols:
        issues.append(ValidationIssue(
            field="columns",
            message=f"Columns with all null values: {null_cols}",
            severity=ValidationSeverity.WARNING
        ))
    
    return issues, records_processed