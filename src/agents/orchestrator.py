# src/agents/orchestrator.py
import os
import asyncio
import time
import uuid
import yaml
import hashlib
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from src.schemas.base_schemas import ValidationResult, ValidationSeverity, DatasetMetadata, Decision
from src.validators.schema_validator import validate_schema, SchemaValidator
from src.validators.rule_validator import RuleValidator
from src.engine.policy_engine import PolicyEngine
from src.agents.human_review_coordinator import HumanReviewCoordinator

from src.monitoring.logging_config import setup_logging, LogContext
from src.monitoring.metrics import (
    ValidationTracker,
    validation_requests_total,
    validation_duration_seconds
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class ValidationStage(str, Enum):
    SCHEMA = "schema"
    RULES = "rules"
    BIO_RULES = "bio_rules"
    BIO_LOOKUPS = "bio_lookups"
    HUMAN_REVIEW = "human_review"
    COMPLETE = "complete"

@dataclass
class OrchestrationConfig:
    """Configuration for orchestration behavior"""
    timeout_seconds: int = 300
    enable_short_circuit: bool = True
    enable_parallel_bio: bool = True
    rules_config_path: Optional[Union[str, Path, Dict[str, Any]]] = None
    policy_config_path: Optional[Union[str, Path, Dict[str, Any]]] = None

class ValidationOrchestrator:
    """
    Orchestrates the validation workflow with short-circuiting and optimized execution.
    This is a genuine "agent" - it makes decisions about workflow execution.
    """
    
    def __init__(self, config: Optional[OrchestrationConfig] = None):
        self.config = config or OrchestrationConfig()
        self.logger = logging.getLogger("orchestrator")
        
        # Initialize logging if not already done
        try:
            setup_logging(
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                log_file="logs/validation.log",
                enable_json=(os.getenv("LOG_FORMAT", "text") == "json")
            )
            self.logger.info("Logging initialized by orchestrator")
        except Exception as e:
            self.logger.debug(f"Logging setup skipped: {e}")
    
        # Log API configuration on startup
        self._log_api_configuration()
        
        # Initialize validators with enhanced config handling
        self._initialize_validators()
        
        self.logger.info("ValidationOrchestrator initialized")
    
    def _initialize_validators(self):
        """Initialize all validators with proper config resolution"""
        # Rule Validator config
        rules_config = self.config.rules_config_path
        if rules_config is None:
            rules_config = Path("config/validation_rules.yml")
            if not rules_config.exists():
                self.logger.warning(f"Rules config not found at {rules_config}, using defaults")
                rules_config = None
        
        # Load and store ruleset metadata
        self.ruleset_metadata = self._load_ruleset_metadata(rules_config)
        
        self.rule_validator = RuleValidator(config=rules_config)
        
        # Policy Engine config
        policy_config = self.config.policy_config_path
        if policy_config is None:
            policy_config = Path("config/policy_config.yml")
            if not policy_config.exists():
                self.logger.warning(f"Policy config not found at {policy_config}, using defaults")
                policy_config = None
        
        self.policy_engine = PolicyEngine(config=policy_config)
        
        # Human Review Coordinator (no config needed)
        self.human_review_coordinator = HumanReviewCoordinator()
    
    def _log_api_configuration(self):
        """Log API key configuration status"""
        ncbi_key = os.getenv('NCBI_API_KEY')
        ensembl_url = os.getenv('ENSEMBL_API_URL', 'https://rest.ensembl.org')
        
        self.logger.info("=" * 60)
        self.logger.info("External API Configuration")
        self.logger.info("=" * 60)
        
        if ncbi_key:
            masked_key = f"{ncbi_key[:8]}...{ncbi_key[-4:]}"
            self.logger.info(f"✅ NCBI API Key: {masked_key}")
            self.logger.info(f"   Rate Limit: 10 requests/second")
            self.logger.info(f"   Performance: 3.3x faster than default")
        else:
            self.logger.warning("⚠️  NCBI API Key: Not configured")
            self.logger.warning("   Rate Limit: 3 requests/second (default)")
            self.logger.warning("   Add NCBI_API_KEY to .env for 3.3x speedup")
        
        self.logger.info(f"Ensembl API: {ensembl_url}")
        self.logger.info("=" * 60)
    
    def _load_ruleset_metadata(self, rules_config_path: Optional[Path]) -> Dict[str, Any]:
        """
        Load ruleset version and metadata from validation_rules.yml
        
        Args:
            rules_config_path: Path to validation rules YAML file
            
        Returns:
            Dictionary with version, last_updated, hash, etc.
        """
        metadata = {
            "version": "unknown",
            "last_updated": "unknown",
            "source": str(rules_config_path) if rules_config_path else "default",
            "hash": None
        }
        
        if not rules_config_path or not Path(rules_config_path).exists():
            self.logger.warning("Rules config not found, using default metadata")
            return metadata
        
        try:
            config_path = Path(rules_config_path)
            
            # Read file content for hashing
            content = config_path.read_text()
            
            # Compute SHA256 hash
            metadata["hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]
            
            # Parse YAML to extract version info
            config = yaml.safe_load(content)
            
            if config and isinstance(config, dict):
                metadata["version"] = config.get("version", "unknown")
                metadata["last_updated"] = config.get("last_updated", "unknown")
                
                # Include changelog summary if available
                if "changelog" in config and config["changelog"]:
                    latest = config["changelog"][0] if config["changelog"] else {}
                    metadata["latest_changes"] = latest.get("changes", [])
            
            self.logger.info(f"✅ Ruleset loaded: v{metadata['version']} (hash: {metadata['hash']})")
            
        except Exception as e:
            self.logger.error(f"Failed to load ruleset metadata: {e}")
        
        return metadata
    
    def suggest_format(self, df: pd.DataFrame) -> str:
        """
        Suggest the best format type for this DataFrame.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            Suggested format_type string
            
        Example:
            >>> orchestrator = ValidationOrchestrator()
            >>> df = pd.read_csv('my_rnaseq_data.csv', index_col=0)
            >>> suggested = orchestrator.suggest_format(df)
            >>> print(f"Detected: {suggested}")
            Detected: generic_matrix
        """
        # Check for GUIDE_RNA format
        guide_rna_cols = {'sequence', 'pam_sequence', 'target_gene'}
        if guide_rna_cols.issubset(set(df.columns)):
            self.logger.info("Detected format: guide_rna (has sequence, pam_sequence, target_gene)")
            return "guide_rna"
        
        # Check for VARIANT_ANNOTATION format
        variant_cols = {'chromosome', 'position', 'ref_allele', 'alt_allele'}
        if variant_cols.issubset(set(df.columns)):
            self.logger.info("Detected format: variant_annotation (has chromosome, position, alleles)")
            return "variant_annotation"
        
        # Check for SAMPLE_METADATA format
        sample_cols = {'sample_id', 'organism'}
        if sample_cols.issubset(set(df.columns)):
            self.logger.info("Detected format: sample_metadata (has sample_id, organism)")
            return "sample_metadata"
        
        # Check if it looks like a matrix (numeric data with gene-like row names)
        if df.shape[0] > 1 and df.shape[1] > 1:
            # Check if most columns are numeric
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) / len(df.columns) > 0.5:
                # Check if index looks like gene names
                if isinstance(df.index[0], str) and 2 <= len(str(df.index[0])) <= 20:
                    self.logger.info("Detected format: generic_matrix (numeric data with gene-like index)")
                    return "generic_matrix"
        
        # Default fallback
        self.logger.info("Format unclear, defaulting to: generic_matrix")
        return "generic_matrix"
    
    def _select_validators(self, format_type: str, metadata: DatasetMetadata) -> List[Any]:
        """
        Select appropriate validators based on data format.
    
        Args:
            format_type: Type of biological data
            metadata: Dataset metadata (for organism, experiment_type, etc.)
        
        Returns:
            List of validator instances
        """
        validators = []
    
        if format_type == "guide_rna":
            from src.validators.bio_rules import BioRulesValidator
            from src.validators.bio_lookups import BioLookupsValidator
        
            validators.extend([
                BioRulesValidator(),
                BioLookupsValidator()
            ])
            self.logger.info("Selected validators: BioRulesValidator, BioLookupsValidator")
    
        elif format_type == "variant_annotation":
            from src.validators.variant_validator import VariantValidator
            reference_genome = metadata.reference_genome or "GRCh38"
            validators.append(VariantValidator(reference_genome=reference_genome))
            self.logger.info(f"Selected validators: VariantValidator (genome: {reference_genome})")
    
        elif format_type == "sample_metadata":
            from src.validators.sample_metadata_validator import SampleMetadataValidator
            validators.append(SampleMetadataValidator(
                require_ontologies=True,
                strict_units=True
            ))
            self.logger.info("Selected validators: SampleMetadataValidator")
        
        elif format_type == "generic_matrix":
            # NEW: Generic matrix validator for any gene-by-sample data
            from src.validators.matrix_validator import MatrixValidator
            
            # Configure based on experiment type
            experiment_type = metadata.experiment_type or ""
            allow_negative = "crispr" in experiment_type.lower() or "screen" in experiment_type.lower()
            
            validators.append(MatrixValidator(
                organism=metadata.organism or "human",
                validate_genes=True,
                allow_negative=allow_negative
            ))
            self.logger.info(f"Selected validators: MatrixValidator (organism: {metadata.organism}, allow_negative: {allow_negative})")
    
        else:
            self.logger.warning(f"Unknown format type: {format_type}, defaulting to generic_matrix")
            from src.validators.matrix_validator import MatrixValidator
            validators.append(MatrixValidator(organism=metadata.organism or "human"))
    
        return validators
    
    async def validate_dataset(
        self,
        dataset: Any,
        metadata: DatasetMetadata
    ) -> Dict[str, Any]:
        """
        Main orchestration method - coordinates all validation with short-circuiting.
        
        Args:
            dataset: The data to validate (DataFrame, list, dict, or file path)
            metadata: Metadata about the dataset
            
        Returns:
            Comprehensive validation report with decision, issues, and metadata
            
        Example:
            >>> orchestrator = ValidationOrchestrator()
            >>> df = pd.read_csv('my_data.csv')
            >>> metadata = DatasetMetadata(
            ...     dataset_id="exp001",
            ...     format_type="generic_matrix",
            ...     record_count=len(df),
            ...     organism="human"
            ... )
            >>> report = await orchestrator.validate_dataset(df, metadata)
            >>> print(report['final_decision'])
            accepted
        """
        start_time = time.time()
        
        # Generate unique validation_id
        validation_id = str(uuid.uuid4())
        
        with LogContext(
            validation_id=validation_id,
            dataset_id=metadata.dataset_id,
            format_type=metadata.format_type,
            record_count=metadata.record_count
        ):
            with ValidationTracker():
                self.logger.info(f"Starting validation {validation_id} for dataset: {metadata.dataset_id}")
                
                # Initialize report
                report = {
                    "validation_id": validation_id,
                    "dataset_id": metadata.dataset_id,
                    "start_time": start_time,
                    "metadata": metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict(),
                    "stages": {},
                    "final_decision": None,
                    "requires_human_review": False,
                    "execution_time_seconds": 0,
                    "short_circuited": False,
                    "decision_rationale": "",
                    
                    # Ruleset versioning for reproducibility
                    "ruleset_metadata": {
                        "version": self.ruleset_metadata.get("version", "unknown"),
                        "last_updated": self.ruleset_metadata.get("last_updated", "unknown"),
                        "source": self.ruleset_metadata.get("source", "unknown"),
                        "hash": self.ruleset_metadata.get("hash", "unknown"),
                        "latest_changes": self.ruleset_metadata.get("latest_changes", [])
                    },
                    
                    "api_configuration": {
                        "ncbi_api_key_configured": bool(os.getenv('NCBI_API_KEY')),
                        "ncbi_rate_limit": "10 req/sec" if os.getenv('NCBI_API_KEY') else "3 req/sec",
                        "cache_enabled": os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
                        "ensembl_fallback_enabled": os.getenv('ENSEMBL_ENABLED', 'true').lower() == 'true'
                    }
                }
                
                try:
                    # Convert dataset to DataFrame if needed
                    df = self._prepare_dataframe(dataset, metadata.format_type)
                    
                    # Stage 1: Schema Validation (BLOCKING - can short-circuit)
                    schema_result = await self._execute_schema_validation(df, metadata, report)
                    
                    if self.config.enable_short_circuit and not schema_result.passed:
                        self.logger.info("Short-circuiting: Schema validation failed")
                        report["short_circuited"] = True
                        report["final_decision"] = Decision.REJECTED.value
                        report["decision_rationale"] = "Failed schema validation"
                        return self._finalize_report(report, start_time)
                    
                    # Stage 2: Rule Validation (BLOCKING - can short-circuit)
                    rule_result = await self._execute_rule_validation(df, metadata, report)
                    
                    if self.config.enable_short_circuit and rule_result.severity == ValidationSeverity.CRITICAL:
                        self.logger.info("Short-circuiting: Critical rule violations detected")
                        report["short_circuited"] = True
                        report["final_decision"] = Decision.REJECTED.value
                        report["decision_rationale"] = "Critical rule violations"
                        return self._finalize_report(report, start_time)
                    
                    # Stage 3+: Get format-specific validators dynamically
                    format_validators = self._select_validators(metadata.format_type, metadata)
                    
                    # Run format-specific validators
                    if self.config.enable_parallel_bio and len(format_validators) > 1:
                        await self._execute_format_validation_parallel(
                            df, metadata, format_validators, report
                        )
                    else:
                        await self._execute_format_validation_sequential(
                            df, metadata, format_validators, report
                        )
                    
                    # Stage 5: Policy-based Decision
                    policy_start = time.time()
                    decision = self.policy_engine.make_decision(report)
                    policy_execution_time = (time.time() - policy_start) * 1000

                    # Ensure decision is always lowercase string
                    decision_value = decision["decision"]
                    if isinstance(decision_value, Decision):
                        decision_value = decision_value.value
                    decision_value = decision_value.lower()

                    report["final_decision"] = decision_value
                    report["decision_rationale"] = decision["rationale"]
                    report["requires_human_review"] = decision["requires_review"]

                    # Add policy stage to report
                    report["stages"]["policy"] = {
                        "validator_name": "PolicyEngine",
                        "passed": decision_value in ["accepted", "conditional_accept"],
                        "severity": "info",
                        "issues": [],
                        "execution_time_ms": policy_execution_time,
                        "records_processed": len(df) if hasattr(df, '__len__') else 0,
                        "metadata": {
                            "decision": decision_value,
                            "rationale": decision["rationale"],
                            "requires_review": decision["requires_review"],
                            "severity_counts": decision.get("severity_counts", {})
                        }
                    }
                    
                    # Stage 6: Human Review if needed
                    if report["requires_human_review"]:
                        self.logger.info(f"Dataset {metadata.dataset_id} flagged for human review")
                        review_result = await self.human_review_coordinator.coordinate_review(
                            report,
                            df
                        )
                        report["stages"]["human_review"] = review_result
            
                        if "decision" in review_result and review_result.get("status") == "completed":
                            review_decision = review_result["decision"]
                            if isinstance(review_decision, Decision):
                                review_decision = review_decision.value
                            report["final_decision"] = review_decision.lower()
                            report["decision_rationale"] = f"Human review override: {review_result.get('feedback', {}).get('comments', '')}"
                            self.logger.info(f"Decision overridden by human review: {report['final_decision']}")
                
                except asyncio.TimeoutError:
                    self.logger.error(f"Validation timeout for dataset {metadata.dataset_id}")
                    report["final_decision"] = "error"
                    report["error"] = "Validation timeout"
                    report["decision_rationale"] = "Validation timed out"
                
                except Exception as e:
                    self.logger.exception(f"Orchestration error for dataset {metadata.dataset_id}: {str(e)}")
                    report["final_decision"] = "error"
                    report["error"] = str(e)
                    report["decision_rationale"] = f"System error: {str(e)}"
                
                # Record validation metrics
                validation_requests_total.labels(
                    dataset_type=metadata.format_type,
                    decision=report.get("final_decision", "error")
                ).inc()
                
                total_duration = time.time() - start_time
                validation_duration_seconds.labels(
                    agent="Orchestrator",
                    stage="complete"
                ).observe(total_duration)
                
                return self._finalize_report(report, start_time)
    
    async def _execute_schema_validation(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        report: Dict
    ) -> ValidationResult:
        """Execute schema validation stage"""
        self.logger.info("Executing schema validation")
        
        result = validate_schema(
            dataset=df,
            schema_type=metadata.format_type,
            strict=True
        )
        
        # Serialize result properly
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
        if 'severity' in result_dict and hasattr(result_dict['severity'], 'value'):
            result_dict['severity'] = result_dict['severity'].value
        
        report["stages"]["schema"] = result_dict
        return result
    
    async def _execute_rule_validation(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        report: Dict
    ) -> ValidationResult:
        """Execute rule-based validation stage"""
        self.logger.info("Executing rule validation")
        
        result = self.rule_validator.validate(
            df, 
            metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        )
        
        # Serialize result properly
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
        if 'severity' in result_dict and hasattr(result_dict['severity'], 'value'):
            result_dict['severity'] = result_dict['severity'].value
        
        report["stages"]["rules"] = result_dict
        return result
    
    async def _execute_format_validation_parallel(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        validators: List[Any],
        report: Dict
    ) -> None:
        """Execute format-specific validators in parallel."""
        self.logger.info(f"Executing {len(validators)} format-specific validators (parallel)")
    
        tasks = []
        validator_info = []
    
        for validator in validators:
            validator_class_name = validator.__class__.__name__
        
            validator_info.append({
                'validator': validator,
                'class_name': validator_class_name,
                'stage_name': validator_class_name.lower().replace('validator', '')
            })
        
            # Determine the right way to call each validator
            if 'Matrix' in validator_class_name:
                # MatrixValidator: async, expects (df, experiment_type)
                experiment_type = metadata.experiment_type or metadata.format_type
                self.logger.debug(f"Setting up MatrixValidator (async, experiment_type: {experiment_type})")
                tasks.append(validator.validate(df, experiment_type))
            
            elif 'BioLookups' in validator_class_name:
                self.logger.debug(f"Setting up BioLookupsValidator (async)")
                tasks.append(validator.validate(df, 'gene_symbols'))
            
            elif 'BioRules' in validator_class_name:
                data_type = metadata.experiment_type or 'guide_rna'
                self.logger.debug(f"Setting up BioRulesValidator (sync, data_type: {data_type})")
                tasks.append(asyncio.to_thread(validator.validate, df, data_type))
            
            elif 'Variant' in validator_class_name:
                self.logger.debug(f"Setting up VariantValidator (sync)")
                tasks.append(asyncio.to_thread(validator.validate, df))
            
            elif 'SampleMetadata' in validator_class_name:
                self.logger.debug(f"Setting up SampleMetadataValidator (sync)")
                tasks.append(asyncio.to_thread(validator.validate, df))
            
            else:
                self.logger.warning(f"Unknown validator type: {validator_class_name}, using generic approach")
                if asyncio.iscoroutinefunction(validator.validate):
                    tasks.append(validator.validate(df))
                else:
                    tasks.append(asyncio.to_thread(validator.validate, df))
    
        # Run all validators concurrently
        self.logger.debug(f"Running {len(tasks)} validation tasks in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
        # Process results
        for info, result in zip(validator_info, results):
            validator_name = info['class_name']
            stage_name = info['stage_name']
        
            # Add appropriate prefix
            if 'bio' in stage_name.lower() and not stage_name.startswith('bio_'):
                stage_name = f"bio_{stage_name}"
            elif 'matrix' in stage_name.lower() and not stage_name.startswith('matrix'):
                stage_name = "matrix"
        
            if isinstance(result, Exception):
                self.logger.error(f"Validator {validator_name} failed: {result}", exc_info=True)
                report["stages"][stage_name] = self._create_error_result(validator_name, result)
            else:
                self.logger.debug(f"Validator {validator_name} completed successfully")
                report["stages"][stage_name] = self._serialize_result(result)
    
    async def _execute_format_validation_sequential(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        validators: List[Any],
        report: Dict
    ) -> None:
        """Execute format-specific validators sequentially."""
        self.logger.info(f"Executing {len(validators)} format-specific validators (sequential)")
        
        for validator in validators:
            validator_name = validator.__class__.__name__
            stage_name = validator_name.lower().replace('validator', '')
            
            # Add appropriate prefix
            if 'matrix' in stage_name:
                stage_name = "matrix"
            
            try:
                if hasattr(validator, 'validate') and asyncio.iscoroutinefunction(validator.validate):
                    # Async validator
                    if 'Matrix' in validator_name:
                        experiment_type = metadata.experiment_type or metadata.format_type
                        result = await validator.validate(df, experiment_type)
                    else:
                        result = await validator.validate(df, 'gene_symbols')
                else:
                    # Sync validator
                    result = validator.validate(df)
                
                report["stages"][stage_name] = self._serialize_result(result)
                
            except Exception as e:
                self.logger.error(f"Validator {validator_name} failed: {e}")
                report["stages"][stage_name] = self._create_error_result(validator_name, e)
    
    def _serialize_result(self, result: Union[ValidationResult, Dict, List]) -> Dict:
        """Serialize ValidationResult to dict with proper enum handling"""
        if isinstance(result, ValidationResult):
            result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
            if 'severity' in result_dict and hasattr(result_dict['severity'], 'value'):
                result_dict['severity'] = result_dict['severity'].value
            return result_dict
        elif isinstance(result, list):
            return {
                "validator_name": "CustomValidator",
                "passed": len(result) == 0,
                "severity": "error" if any(
                    getattr(issue, 'severity', 'info') in ['error', 'critical'] 
                    for issue in result
                ) else "info",
                "issues": [
                    issue.model_dump() if hasattr(issue, 'model_dump') else issue 
                    for issue in result
                ],
                "execution_time_ms": 0,
                "records_processed": 0
            }
        return result
    
    def _prepare_dataframe(self, dataset: Any, format_type: str) -> pd.DataFrame:
        """Convert dataset to DataFrame for processing"""
        if isinstance(dataset, pd.DataFrame):
            return dataset
        elif isinstance(dataset, list):
            return pd.DataFrame(dataset)
        elif isinstance(dataset, dict):
            return pd.DataFrame([dataset])
        elif isinstance(dataset, str) and format_type == 'fasta':
            from Bio import SeqIO
            from io import StringIO
            records = list(SeqIO.parse(StringIO(dataset), "fasta"))
            return pd.DataFrame([
                {
                    'id': r.id,
                    'sequence': str(r.seq),
                    'description': r.description
                }
                for r in records
            ])
        else:
            raise ValueError(f"Cannot convert {type(dataset)} to DataFrame")
    
    def _finalize_report(self, report: Dict, start_time: float) -> Dict:
        """Finalize the validation report"""
        report["execution_time_seconds"] = time.time() - start_time
        report["end_time"] = time.time()
        
        if report["final_decision"]:
            decision = report["final_decision"]
            if isinstance(decision, Decision):
                decision = decision.value
            report["final_decision"] = decision.lower()
        
        self.logger.info(
            f"Validation complete for {report['dataset_id']}: "
            f"{report['final_decision']} in {report['execution_time_seconds']:.2f}s"
        )
        
        return report

    def _create_error_result(self, validator_name: str, error: Exception) -> Dict:
        """Create error result for failed validator"""
        return {
            "validator_name": validator_name,
            "passed": False,
            "severity": "error",
            "issues": [{"message": str(error), "severity": "error", "field": "system"}],
            "execution_time_ms": 0,
            "records_processed": 0,
            "metadata": {}
        }