# src/api/models.py
"""
Pydantic models for API request/response validation.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum


class ValidationFormat(str, Enum):
    """Supported data formats"""
    FASTA = "fasta"
    FASTQ = "fastq"
    GENBANK = "genbank"
    GUIDE_RNA = "guide_rna"
    JSON = "json"
    CSV = "csv"
    TABULAR = "tabular"


class ValidationStatus(str, Enum):
    """Validation request status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Decision(str, Enum):
    """Final validation decision"""
    ACCEPTED = "ACCEPTED"
    CONDITIONAL_ACCEPT = "CONDITIONAL_ACCEPT"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    ERROR = "ERROR"


# Request Models
class ValidationRequest(BaseModel):
    """Request to validate a dataset"""
    format: ValidationFormat
    data: Union[str, List[Dict[str, Any]], Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    strict: bool = Field(default=True, description="Stop on first error")
    enable_short_circuit: bool = Field(default=True)
    enable_parallel_bio: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "format": "guide_rna",
                "data": [{
                    "guide_id": "gRNA_001",
                    "sequence": "ATCGATCGATCGATCGATCG",
                    "pam_sequence": "AGG",
                    "target_gene": "BRCA1",
                    "organism": "human",
                    "nuclease_type": "SpCas9"
                }],
                "metadata": {
                    "experiment_id": "EXP_001",
                    "researcher": "Dr. Smith"
                },
                "strict": True
            }
        }


class FileUploadRequest(BaseModel):
    """Request to validate uploaded file"""
    format: ValidationFormat
    filename: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


# Response Models
class ValidationSubmitResponse(BaseModel):
    """Response after submitting validation request"""
    validation_id: str
    status: ValidationStatus
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion_seconds: Optional[int] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class IssueResponse(BaseModel):
    """Validation issue in response"""
    field: str
    message: str
    severity: str
    rule_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StageResponse(BaseModel):
    """Validation stage result in response"""
    validator_name: str
    passed: bool
    severity: str
    issues: List[IssueResponse]
    execution_time_ms: float
    records_processed: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationReportResponse(BaseModel):
    """Complete validation report"""
    dataset_id: str
    validation_id: str
    start_time: float
    end_time: float
    execution_time_seconds: float
    final_decision: Decision
    requires_human_review: bool
    short_circuited: bool
    stages: Dict[str, StageResponse]
    decision_rationale: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationStatusResponse(BaseModel):
    """Response for validation status check"""
    validation_id: str
    status: ValidationStatus
    progress_percent: Optional[int] = None
    current_stage: Optional[str] = None
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    report: Optional[ValidationReportResponse] = None
    error: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, str] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class MetricsResponse(BaseModel):
    """System metrics response"""
    total_validations: int
    validations_today: int
    average_execution_time_seconds: float
    success_rate_percent: float
    active_validations: int
    human_reviews_pending: int


class BatchValidationRequest(BaseModel):
    """Request to validate multiple datasets"""
    datasets: List[ValidationRequest]
    parallel: bool = Field(default=True)
    max_parallel: int = Field(default=4, ge=1, le=10)


class BatchValidationResponse(BaseModel):
    """Response for batch validation"""
    batch_id: str
    total_datasets: int
    validation_ids: List[str]
    status: ValidationStatus


# Error Models
class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }