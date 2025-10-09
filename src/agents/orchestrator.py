# src/agents/orchestrator.py
import os
import asyncio
import time
import uuid
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
from src.validators.bio_rules import BioRulesValidator
from src.validators.bio_lookups import BioLookupsValidator
from src.engine.policy_engine import PolicyEngine
from src.agents.human_review_coordinator import HumanReviewCoordinator

# ═══════════════════════════════════════════════════════════════════════════
# MONITORING IMPORTS - ADDED FOR STEP 2
# ═══════════════════════════════════════════════════════════════════════════
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
        
        # ═══════════════════════════════════════════════════════════════════
        # MONITORING SETUP - ADDED FOR STEP 2
        # ═══════════════════════════════════════════════════════════════════
        # Initialize logging if not already done
        try:
            setup_logging(
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                log_file="logs/validation.log",
                enable_json=(os.getenv("LOG_FORMAT", "text") == "json")
            )
            self.logger.info("Logging initialized by orchestrator")
        except Exception as e:
            # Already initialized or error - continue
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
        
        self.rule_validator = RuleValidator(config=rules_config)
        
        # Bio validators (no config needed)
        self.bio_rules = BioRulesValidator()
        self.bio_lookups = BioLookupsValidator()
        
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
    
    async def validate_dataset(
        self,
        dataset: Any,
        metadata: DatasetMetadata
    ) -> Dict[str, Any]:
        """
        Main orchestration method - coordinates all validation with short-circuiting.
        
        Args:
            dataset: The data to validate
            metadata: Metadata about the dataset
            
        Returns:
            Comprehensive validation report
        """
        start_time = time.time()
        
        # Generate unique validation_id
        validation_id = str(uuid.uuid4())
        
        # ═══════════════════════════════════════════════════════════════════
        # MONITORING: Add logging context - ADDED FOR STEP 2
        # ═══════════════════════════════════════════════════════════════════
        with LogContext(
            validation_id=validation_id,
            dataset_id=metadata.dataset_id,
            format_type=metadata.format_type,
            record_count=metadata.record_count
        ):
            # ═══════════════════════════════════════════════════════════════
            # MONITORING: Track active validation - ADDED FOR STEP 2
            # ═══════════════════════════════════════════════════════════════
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
                    "api_configuration": {
                        "ncbi_api_key_configured": bool(os.getenv('NCBI_API_KEY')),
                        "ncbi_rate_limit": "10 req/sec" if os.getenv('NCBI_API_KEY') else "3 req/sec"
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
                    
                    # Stage 3 & 4: Biological Validation (Parallel if enabled)
                    if self.config.enable_parallel_bio:
                        bio_results = await self._execute_bio_validation_parallel(df, metadata, report)
                    else:
                        bio_results = await self._execute_bio_validation_sequential(df, metadata, report)
                    
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
            
                        # Only override if there's a REAL completed human review with a decision
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
                
                # ═══════════════════════════════════════════════════════════
                # MONITORING: Record validation request metric - ADDED
                # ═══════════════════════════════════════════════════════════
                validation_requests_total.labels(
                    dataset_type=metadata.format_type,
                    decision=report.get("final_decision", "error")
                ).inc()
                
                # Record overall validation duration
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
    
    async def _execute_bio_validation_parallel(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        report: Dict
    ) -> Dict[str, ValidationResult]:
        """Execute biological validations in parallel"""
        self.logger.info("Executing biological validations (parallel)")
        
        # Run local and external validations concurrently
        bio_rules_task = asyncio.create_task(
            asyncio.to_thread(self.bio_rules.validate, df, metadata.experiment_type or 'guide_rna')
        )
        bio_lookups_task = self.bio_lookups.validate(df, 'gene_symbols')
        
        results = await asyncio.gather(bio_rules_task, bio_lookups_task, return_exceptions=True)
        
        # Process results
        bio_rules_result = results[0] if not isinstance(results[0], Exception) else self._create_error_result("BioRules", results[0])
        bio_lookups_result = results[1] if not isinstance(results[1], Exception) else self._create_error_result("BioLookups", results[1])
        
        # Serialize results
        bio_rules_dict = self._serialize_result(bio_rules_result)
        bio_lookups_dict = self._serialize_result(bio_lookups_result)
        
        report["stages"]["bio_rules"] = bio_rules_dict
        report["stages"]["bio_lookups"] = bio_lookups_dict
        
        return {
            "bio_rules": bio_rules_result,
            "bio_lookups": bio_lookups_result
        }
    
    async def _execute_bio_validation_sequential(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        report: Dict
    ) -> Dict[str, ValidationResult]:
        """Execute biological validations sequentially"""
        self.logger.info("Executing biological validations (sequential)")
        
        # Local checks first (fast)
        bio_rules_result = self.bio_rules.validate(df, metadata.experiment_type or 'guide_rna')
        report["stages"]["bio_rules"] = self._serialize_result(bio_rules_result)
        
        # External lookups second (slower)
        bio_lookups_result = await self.bio_lookups.validate(df, 'gene_symbols')
        report["stages"]["bio_lookups"] = self._serialize_result(bio_lookups_result)
        
        return {
            "bio_rules": bio_rules_result,
            "bio_lookups": bio_lookups_result
        }
    
    def _serialize_result(self, result: Union[ValidationResult, Dict]) -> Dict:
        """Serialize ValidationResult to dict with proper enum handling"""
        if isinstance(result, ValidationResult):
            result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
            if 'severity' in result_dict and hasattr(result_dict['severity'], 'value'):
                result_dict['severity'] = result_dict['severity'].value
            return result_dict
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
            # Parse FASTA and convert to DataFrame
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
        
        # Ensure final_decision is lowercase string
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