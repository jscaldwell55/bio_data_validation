# src/schemas/base_schemas.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ValidationIssue(BaseModel):
    """Single validation issue"""
    field: str
    message: str
    severity: ValidationSeverity
    rule_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ValidationResult(BaseModel):
    """Standardized validation result"""
    validator_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    passed: bool
    severity: ValidationSeverity
    issues: List[ValidationIssue] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float
    records_processed: int = 0

class DatasetMetadata(BaseModel):
    """Metadata about the dataset being validated"""
    dataset_id: str
    format_type: str
    record_count: int
    source: Optional[str] = None
    organism: Optional[str] = None
    experiment_type: Optional[str] = None