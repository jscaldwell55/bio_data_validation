# tests/builders.py
"""
Test data builders for creating complex test objects easily.
Implements the Builder pattern to make tests more readable and maintainable.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.schemas.base_schemas import (
    ValidationIssue,
    ValidationSeverity,
    ValidationResult,
    Decision,
    ReviewPriority
)


class ValidationIssueBuilder:
    """Builder for creating ValidationIssue objects."""
    
    def __init__(self):
        self._field = "test_field"
        self._message = "Test issue"
        self._severity = ValidationSeverity.INFO
        self._rule_id = None
        self._metadata = {}
    
    def with_field(self, field: str):
        """Set the field name."""
        self._field = field
        return self
    
    def with_message(self, message: str):
        """Set the message."""
        self._message = message
        return self
    
    def with_severity(self, severity: ValidationSeverity):
        """Set the severity."""
        self._severity = severity
        return self
    
    def critical(self):
        """Make this a critical issue."""
        self._severity = ValidationSeverity.CRITICAL
        return self
    
    def error(self):
        """Make this an error issue."""
        self._severity = ValidationSeverity.ERROR
        return self
    
    def warning(self):
        """Make this a warning issue."""
        self._severity = ValidationSeverity.WARNING
        return self
    
    def info(self):
        """Make this an info issue."""
        self._severity = ValidationSeverity.INFO
        return self
    
    def with_rule_id(self, rule_id: str):
        """Set the rule ID."""
        self._rule_id = rule_id
        return self
    
    def with_metadata(self, metadata: Dict[str, Any]):
        """Set metadata."""
        self._metadata = metadata
        return self
    
    def build(self) -> ValidationIssue:
        """Build the ValidationIssue."""
        return ValidationIssue(
            field=self._field,
            message=self._message,
            severity=self._severity,
            rule_id=self._rule_id,
            metadata=self._metadata
        )


class ValidationResultBuilder:
    """Builder for creating ValidationResult objects."""
    
    def __init__(self):
        self._validator_name = "TestValidator"
        self._passed = True
        self._severity = ValidationSeverity.INFO
        self._issues = []
        self._execution_time_ms = 100.0
        self._records_processed = 0
        self._metadata = {}
    
    def with_validator_name(self, name: str):
        """Set validator name."""
        self._validator_name = name
        return self
    
    def passed(self, passed: bool = True):
        """Set passed status."""
        self._passed = passed
        return self
    
    def failed(self):
        """Mark as failed."""
        self._passed = False
        return self
    
    def with_severity(self, severity: ValidationSeverity):
        """Set overall severity."""
        self._severity = severity
        return self
    
    def with_issues(self, issues: List[ValidationIssue]):
        """Set issues list."""
        self._issues = issues
        return self
    
    def add_issue(self, issue: ValidationIssue):
        """Add a single issue."""
        self._issues.append(issue)
        return self
    
    def with_execution_time(self, ms: float):
        """Set execution time."""
        self._execution_time_ms = ms
        return self
    
    def with_records_processed(self, count: int):
        """Set records processed count."""
        self._records_processed = count
        return self
    
    def with_metadata(self, metadata: Dict[str, Any]):
        """Set metadata."""
        self._metadata = metadata
        return self
    
    def build(self) -> ValidationResult:
        """Build the ValidationResult."""
        return ValidationResult(
            validator_name=self._validator_name,
            passed=self._passed,
            severity=self._severity,
            issues=self._issues,
            execution_time_ms=self._execution_time_ms,
            records_processed=self._records_processed,
            metadata=self._metadata
        )


class ValidationReportBuilder:
    """Builder for creating validation report dictionaries."""
    
    def __init__(self):
        self._validation_id = "test-validation-001"
        self._dataset_id = "test-dataset-001"
        self._start_time = datetime.now().timestamp()
        self._stages = {}
        self._final_decision = Decision.ACCEPTED.value
        self._requires_human_review = False
        self._short_circuited = False
        self._decision_rationale = "All checks passed"
    
    def with_validation_id(self, validation_id: str):
        """Set validation ID."""
        self._validation_id = validation_id
        return self
    
    def with_dataset_id(self, dataset_id: str):
        """Set dataset ID."""
        self._dataset_id = dataset_id
        return self
    
    def with_decision(self, decision: str):
        """Set final decision."""
        if isinstance(decision, Decision):
            self._final_decision = decision.value
        else:
            self._final_decision = decision
        return self
    
    def accepted(self):
        """Mark as accepted."""
        self._final_decision = Decision.ACCEPTED.value
        self._decision_rationale = "All validation checks passed"
        return self
    
    def rejected(self):
        """Mark as rejected."""
        self._final_decision = Decision.REJECTED.value
        self._decision_rationale = "Validation failed"
        return self
    
    def conditional_accept(self):
        """Mark as conditional accept."""
        self._final_decision = Decision.CONDITIONAL_ACCEPT.value
        self._decision_rationale = "Accepted with warnings"
        return self
    
    def with_human_review(self, required: bool = True):
        """Set human review requirement."""
        self._requires_human_review = required
        return self
    
    def short_circuited(self, value: bool = True):
        """Set short-circuit status."""
        self._short_circuited = value
        return self
    
    def with_schema_passed(self):
        """Add passing schema stage."""
        self._stages['schema'] = {
            'validator_name': 'SchemaValidator',
            'passed': True,
            'severity': 'info',
            'issues': [],
            'execution_time_ms': 50.0,
            'records_processed': 10
        }
        return self
    
    def with_schema_failed(self):
        """Add failing schema stage."""
        self._stages['schema'] = {
            'validator_name': 'SchemaValidator',
            'passed': False,
            'severity': 'error',
            'issues': [{
                'field': 'schema',
                'message': 'Schema validation failed',
                'severity': 'error'
            }],
            'execution_time_ms': 50.0,
            'records_processed': 10
        }
        return self
    
    def with_errors(self, count: int, stage_name: str = 'rules'):
        """Add errors to specified stage."""
        issues = [
            {
                'field': f'field_{i}',
                'message': f'Error {i}',
                'severity': 'error',
                'rule_id': f'ERR_{i:03d}'
            }
            for i in range(count)
        ]
        
        self._stages[stage_name] = {
            'validator_name': stage_name.title() + 'Validator',
            'passed': False,
            'severity': 'error',
            'issues': issues,
            'execution_time_ms': 100.0,
            'records_processed': 10
        }
        return self
    
    def with_warnings(self, count: int, stage_name: str = 'bio_rules'):
        """Add warnings to specified stage."""
        issues = [
            {
                'field': f'field_{i}',
                'message': f'Warning {i}',
                'severity': 'warning',
                'rule_id': f'WARN_{i:03d}'
            }
            for i in range(count)
        ]
        
        self._stages[stage_name] = {
            'validator_name': stage_name.title() + 'Validator',
            'passed': True,
            'severity': 'warning',
            'issues': issues,
            'execution_time_ms': 100.0,
            'records_processed': 10
        }
        return self
    
    def with_critical_issue(self, stage_name: str = 'schema'):
        """Add critical issue to specified stage."""
        self._stages[stage_name] = {
            'validator_name': stage_name.title() + 'Validator',
            'passed': False,
            'severity': 'critical',
            'issues': [{
                'field': 'system',
                'message': 'Critical system error',
                'severity': 'critical',
                'rule_id': 'CRIT_001'
            }],
            'execution_time_ms': 100.0,
            'records_processed': 0
        }
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the validation report dictionary."""
        end_time = self._start_time + 1.5
        return {
            'validation_id': self._validation_id,
            'dataset_id': self._dataset_id,
            'start_time': self._start_time,
            'end_time': end_time,
            'execution_time_seconds': end_time - self._start_time,
            'final_decision': self._final_decision,
            'requires_human_review': self._requires_human_review,
            'short_circuited': self._short_circuited,
            'decision_rationale': self._decision_rationale,
            'stages': self._stages,
            'metadata': {}
        }


class DataFrameBuilder:
    """Builder for creating test DataFrames with guide RNA data."""
    
    def __init__(self):
        self._n_records = 10
        self._sequences = None
        self._pam_sequences = None
        self._target_genes = None
        self._organisms = None
        self._nuclease_types = None
        self._gc_contents = None
        self._efficiency_scores = None
        self._has_duplicates = False
        self._has_invalid_pam = False
        self._has_invalid_sequence = False
    
    def with_n_guides(self, n: int):
        """Set number of guide RNAs."""
        self._n_records = n
        return self
    
    def with_sequences(self, sequences: List[str]):
        """Set specific sequences."""
        self._sequences = sequences
        self._n_records = len(sequences)
        return self
    
    def with_duplicates(self):
        """Include duplicate guide IDs."""
        self._has_duplicates = True
        return self
    
    def with_invalid_pam(self):
        """Include invalid PAM sequences."""
        self._has_invalid_pam = True
        return self
    
    def with_invalid_sequence(self):
        """Include invalid sequence characters."""
        self._has_invalid_sequence = True
        return self
    
    def build(self) -> pd.DataFrame:
        """Build the DataFrame."""
        # Generate guide IDs
        if self._has_duplicates:
            guide_ids = [f'gRNA_{i:03d}' for i in range(self._n_records - 1)]
            guide_ids.append(guide_ids[0])  # Duplicate first ID
        else:
            guide_ids = [f'gRNA_{i:03d}' for i in range(self._n_records)]
        
        # Generate sequences
        if self._sequences:
            sequences = self._sequences
        elif self._has_invalid_sequence:
            sequences = ['ATCGATCGATCGATCGATCG'] * (self._n_records - 1)
            sequences.append('INVALID123')  # Invalid sequence
        else:
            sequences = ['ATCGATCGATCGATCGATCG'] * self._n_records
        
        # Generate PAM sequences
        if self._has_invalid_pam:
            pam_sequences = ['AGG'] * (self._n_records - 1)
            pam_sequences.append('XXX')  # Invalid PAM
        else:
            pam_sequences = ['AGG'] * self._n_records
        
        # Generate other fields
        target_genes = self._target_genes or (['BRCA1'] * self._n_records)
        organisms = self._organisms or (['human'] * self._n_records)
        nuclease_types = self._nuclease_types or (['SpCas9'] * self._n_records)
        gc_contents = self._gc_contents or ([0.5] * self._n_records)
        efficiency_scores = self._efficiency_scores or ([0.85] * self._n_records)
        
        return pd.DataFrame({
            'guide_id': guide_ids,
            'sequence': sequences,
            'pam_sequence': pam_sequences,
            'target_gene': target_genes,
            'organism': organisms,
            'nuclease_type': nuclease_types,
            'gc_content': gc_contents,
            'efficiency_score': efficiency_scores,
            'start_position': list(range(1000000, 1000000 + self._n_records)),
            'end_position': list(range(1000020, 1000020 + self._n_records))
        })