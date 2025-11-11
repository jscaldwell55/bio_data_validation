# src/schemas/base_schemas.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime
from enum import Enum
import yaml


class SerializableEnum(str, Enum):
    """
    Base class for all enums with automatic .value conversion.
    Eliminates enum comparison failures in tests and reports.

    Usage:
        class MyEnum(SerializableEnum):
            VALUE1 = "value1"
            VALUE2 = "value2"

    Benefits:
        - Automatic string conversion for comparisons
        - JSON serialization works out of the box
        - No more .value access needed in comparisons
        - Flexible deserialization from both enum and string values
    """

    def to_dict(self) -> str:
        """Convert to dict-safe value for JSON serialization"""
        return self.value

    @classmethod
    def from_value(cls, value: Any):
        """
        Create enum from value, handling both enum and string inputs.

        Args:
            value: Either an enum instance of this class or a string value

        Returns:
            Enum instance

        Raises:
            ValueError: If value cannot be converted to this enum type
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(value)
        raise ValueError(f"Cannot convert {value} to {cls.__name__}")

    def __str__(self) -> str:
        """Return the enum value as string"""
        return self.value

    def __eq__(self, other) -> bool:
        """Compare enum by value, supporting both enum and string comparisons"""
        if isinstance(other, Enum):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        """Make enum hashable by its value"""
        return hash(self.value)


class ConfigurableComponent:
    """
    Base class for components that accept flexible configuration from file, dict, or defaults.
    Eliminates need for file mocking in tests and provides a unified initialization pattern.

    Usage:
        class MyComponent(ConfigurableComponent):
            def __init__(
                self,
                config: Optional[Union[str, Path, Dict[str, Any]]] = None,
                **kwargs
            ):
                super().__init__(config, **kwargs)
                # Extract specific configurations
                self.specific_param = self.config.get('specific_param', 'default')

            def _get_default_config(self) -> Dict[str, Any]:
                return {'specific_param': 'default_value'}

    Benefits:
        - Tests can pass dict directly without file mocking
        - Production code can use file paths
        - Supports parameter overrides via **kwargs
        - Consistent config loading pattern across all components
    """

    def __init__(
        self,
        config: Optional[Union[str, Path, Dict[str, Any]]] = None,
        strict: bool = False,
        **kwargs
    ):
        """
        Initialize with flexible configuration input.

        Args:
            config: Can be:
                - str/Path: Path to YAML configuration file
                - dict: Configuration dictionary (for testing)
                - None: Use default configuration
            strict: If True, raise YAMLError for malformed YAML instead of ValueError
            **kwargs: Override specific config values
        """
        import logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.strict = strict

        # Load base configuration
        if config is None:
            self.config = self._get_default_config()
        elif isinstance(config, (str, Path)):
            self.config = self._load_from_file(config)
        elif isinstance(config, dict):
            self.config = config.copy()  # Use a copy to avoid mutating input
        else:
            raise TypeError(f"config must be str, Path, dict, or None, got {type(config)}")

        # Allow kwargs to override specific values (excluding strict)
        config_kwargs = {k: v for k, v in kwargs.items() if k != 'strict'}
        self.config.update(config_kwargs)

        # Validate configuration
        self._validate_config()

    def _load_from_file(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Load configuration from YAML file with error handling."""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {path}, using defaults")
            return self._get_default_config()
        except yaml.YAMLError as e:
            self.logger.error(f"Invalid YAML in {path}: {e}")
            if self.strict:
                raise  # Re-raise the original YAMLError in strict mode
            raise ValueError(f"Failed to parse config file: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration. Override in subclasses."""
        return {}

    def _validate_config(self):
        """Validate configuration. Override in subclasses."""
        pass


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively serialize objects for JSON/dict storage.
    Handles enums, Pydantic models, dataclasses, etc.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable value (str, int, float, bool, None, list, or dict)

    Usage:
        report = {"decision": Decision.ACCEPTED, "severity": ValidationSeverity.ERROR}
        serialized = serialize_for_json(report)
        # serialized = {"decision": "accepted", "severity": "error"}
    """
    if isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, 'model_dump'):  # Pydantic v2
        return obj.model_dump()
    elif hasattr(obj, 'dict'):  # Pydantic v1
        return obj.dict()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


def deserialize_enum(value: Any, enum_class: type[Enum]) -> Enum:
    """
    Safely deserialize enum from string or enum instance.

    Args:
        value: Either an enum instance or string value
        enum_class: The enum class to deserialize to

    Returns:
        Enum instance

    Raises:
        ValueError: If value cannot be converted to enum

    Usage:
        decision = deserialize_enum("accepted", Decision)
        # decision = Decision.ACCEPTED
    """
    if isinstance(value, enum_class):
        return value
    return enum_class(value)


class ValidationSeverity(SerializableEnum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Decision(SerializableEnum):
    """Final validation decision"""
    ACCEPTED = "accepted"
    CONDITIONAL_ACCEPT = "conditional_accept"
    REJECTED = "rejected"


class ValidationStatus(SerializableEnum):
    """Status of validation run"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FormatType(SerializableEnum):
    """
    Supported data format types.
    
    🆕 GENERIC_MATRIX - New universal validator for any gene-by-sample matrix data.
    Supports: RNA-seq, proteomics, CRISPR screens, drug response, metabolomics, etc.
    """
    FASTA = "fasta"
    FASTQ = "fastq"
    GENBANK = "genbank"
    GUIDE_RNA = "guide_rna"
    CSV = "csv"
    JSON = "json"
    TABULAR = "tabular"
    VARIANT_ANNOTATION = "variant_annotation"
    SAMPLE_METADATA = "sample_metadata"
    GENERIC_MATRIX = "generic_matrix"  # 🆕 NEW: Universal gene-by-sample validator


class ReviewPriority(SerializableEnum):
    """Priority levels for human review"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(SerializableEnum):
    """Status of human review"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class ValidationIssue(BaseModel):
    """Single validation issue"""
    field: str
    message: str
    severity: ValidationSeverity
    rule_id: Optional[str] = None
    affected_records: int = 0
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
    reference_genome: Optional[str] = None  # For variant data
    additional_metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Complete validation report"""
    dataset_id: str
    validation_id: str
    start_time: float
    end_time: float
    execution_time_seconds: float
    final_decision: Decision
    requires_human_review: bool
    short_circuited: bool
    stages: Dict[str, Any] = Field(default_factory=dict)
    decision_rationale: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationStageResult(BaseModel):
    """Result from a single validation stage"""
    stage_name: str
    validator_name: str
    passed: bool
    severity: ValidationSeverity
    issues: List[ValidationIssue] = Field(default_factory=list)
    execution_time_ms: float
    records_processed: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewTask(BaseModel):
    """Human review task"""
    review_id: str
    validation_id: str
    priority: ReviewPriority
    status: ReviewStatus
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    issues: List[ValidationIssue] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    feedback: Optional[Dict[str, Any]] = None