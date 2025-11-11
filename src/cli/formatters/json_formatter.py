"""JSON formatter for validation results"""

import json
from datetime import datetime
from typing import Dict, Any
from src.schemas.base_schemas import ValidationResult, ValidationIssue, ValidationSeverity


class JSONFormatter:
    """Format validation results as JSON"""

    def __init__(self, pretty: bool = True):
        """
        Initialize JSON formatter.

        Args:
            pretty: Whether to pretty-print JSON
        """
        self.pretty = pretty

    def format(self, result: ValidationResult) -> str:
        """
        Format validation result as JSON.

        Args:
            result: ValidationResult from validator

        Returns:
            JSON string
        """
        output = {
            "validation_report": {
                "metadata": {
                    "validator": result.validator_name,
                    "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                    "version": "0.1.0"
                },
                "status": "passed" if result.passed else "failed",
                "severity": result.severity.value,
                "execution_time_seconds": result.execution_time_ms / 1000,
                "records_processed": result.records_processed,
                "dataset_info": result.metadata or {},
                "issues": self._format_issues(result.issues),
                "summary": {
                    "total_issues": len(result.issues),
                    "by_severity": self._count_by_severity(result.issues)
                }
            }
        }

        if self.pretty:
            return json.dumps(output, indent=2, default=str)
        else:
            return json.dumps(output, default=str)

    def _format_issues(self, issues: list) -> list:
        """Format issues for JSON output"""
        formatted = []

        for issue in issues:
            formatted.append({
                "field": issue.field,
                "severity": issue.severity.value,
                "message": issue.message,
                "affected_records": issue.affected_records,
                "metadata": issue.metadata or {}
            })

        return formatted

    def _count_by_severity(self, issues: list) -> Dict[str, int]:
        """Count issues by severity"""
        counts = {
            "critical": 0,
            "error": 0,
            "warning": 0,
            "info": 0
        }

        for issue in issues:
            severity = issue.severity.value
            if severity in counts:
                counts[severity] += 1

        return counts
