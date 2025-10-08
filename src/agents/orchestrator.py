# src/agents/orchestrator.py
import asyncio
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

from src.schemas.base_schemas import ValidationResult, ValidationSeverity, DatasetMetadata
from src.validators.schema_validator import validate_schema
from src.validators.rule_validator import RuleValidator
from src.validators.bio_rules import BioRules
from src.validators.bio_lookups import BioLookups
from src.engine.policy_engine import PolicyEngine
from src.agents.human_review_coordinator import HumanReviewCoordinator

logger = logging.getLogger(__name__)

class ValidationStage(str, Enum):
    SCHEMA = "schema"
    RULES = "rules"
    BIO_LOCAL = "bio_local"
    BIO_EXTERNAL = "bio_external"
    HUMAN_REVIEW = "human_review"
    COMPLETE = "complete"

@dataclass
class OrchestrationConfig:
    """Configuration for orchestration behavior"""
    timeout_seconds: int = 300
    enable_short_circuit: bool = True
    enable_parallel_bio: bool = True
    rules_config_path: str = "config/validation_rules.yml"
    policy_config_path: str = "config/policy_config.yml"

class ValidationOrchestrator:
    """
    Orchestrates the validation workflow with short-circuiting and optimized execution.
    This is a genuine "agent" - it makes decisions about workflow execution.
    """
    
    def __init__(self, config: Optional[OrchestrationConfig] = None):
        self.config = config or OrchestrationConfig()
        self.logger = logging.getLogger("orchestrator")
        
        # Initialize validators
        self.rule_validator = RuleValidator(self.config.rules_config_path)
        self.bio_rules = BioRules()
        self.bio_lookups = BioLookups()
        
        # Initialize policy engine and human review coordinator
        self.policy_engine = PolicyEngine(self.config.policy_config_path)
        self.human_review_coordinator = HumanReviewCoordinator()
        
        self.logger.info("ValidationOrchestrator initialized")
    
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
        self.logger.info(f"Starting validation for dataset: {metadata.dataset_id}")
        
        # Initialize report
        report = {
            "dataset_id": metadata.dataset_id,
            "start_time": time.time(),
            "metadata": metadata.dict(),
            "stages": {},
            "final_decision": None,
            "requires_human_review": False,
            "execution_time_seconds": 0,
            "short_circuited": False
        }
        
        try:
            # Convert dataset to DataFrame if needed
            df = self._prepare_dataframe(dataset, metadata.format_type)
            
            # Stage 1: Schema Validation (BLOCKING - can short-circuit)
            schema_result = await self._execute_schema_validation(df, metadata, report)
            
            if self.config.enable_short_circuit and not schema_result.passed:
                self.logger.info("Short-circuiting: Schema validation failed")
                report["short_circuited"] = True
                report["final_decision"] = "REJECTED"
                report["rejection_reason"] = "Failed schema validation"
                return self._finalize_report(report, start_time)
            
            # Stage 2: Rule Validation (BLOCKING - can short-circuit)
            rule_result = await self._execute_rule_validation(df, metadata, report)
            
            if self.config.enable_short_circuit and rule_result.severity == ValidationSeverity.CRITICAL:
                self.logger.info("Short-circuiting: Critical rule violations detected")
                report["short_circuited"] = True
                report["final_decision"] = "REJECTED"
                report["rejection_reason"] = "Critical rule violations"
                return self._finalize_report(report, start_time)
            
            # Stage 3 & 4: Biological Validation (Parallel if enabled)
            if self.config.enable_parallel_bio:
                bio_results = await self._execute_bio_validation_parallel(df, metadata, report)
            else:
                bio_results = await self._execute_bio_validation_sequential(df, metadata, report)
            
            # Stage 5: Policy-based Decision
            decision = self.policy_engine.make_decision(report)
            report["final_decision"] = decision["decision"]
            report["decision_rationale"] = decision["rationale"]
            report["requires_human_review"] = decision["requires_review"]
            
            # Stage 6: Human Review if needed
            if report["requires_human_review"]:
                self.logger.info(f"Dataset {metadata.dataset_id} flagged for human review")
                review_result = await self.human_review_coordinator.coordinate_review(
                    report,
                    df
                )
                report["stages"]["human_review"] = review_result
                report["final_decision"] = review_result.get("decision", "PENDING_REVIEW")
        
        except asyncio.TimeoutError:
            self.logger.error(f"Validation timeout for dataset {metadata.dataset_id}")
            report["final_decision"] = "ERROR"
            report["error"] = "Validation timeout"
        
        except Exception as e:
            self.logger.exception(f"Orchestration error for dataset {metadata.dataset_id}: {str(e)}")
            report["final_decision"] = "ERROR"
            report["error"] = str(e)
        
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
        
        report["stages"]["schema"] = result.dict()
        return result
    
    async def _execute_rule_validation(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata,
        report: Dict
    ) -> ValidationResult:
        """Execute rule-based validation stage"""
        self.logger.info("Executing rule validation")
        
        result = self.rule_validator.validate(df, metadata.dict())
        
        report["stages"]["rules"] = result.dict()
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
        tasks = [
            self.bio_rules.validate(df, metadata.experiment_type or 'guide_rna'),
            self.bio_lookups.validate(df, 'gene_symbols')
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        bio_local_result = results[0] if not isinstance(results[0], Exception) else self._create_error_result("BioRules", results[0])
        bio_external_result = results[1] if not isinstance(results[1], Exception) else self._create_error_result("BioLookups", results[1])
        
        report["stages"]["bio_local"] = bio_local_result.dict() if isinstance(bio_local_result, ValidationResult) else bio_local_result
        report["stages"]["bio_external"] = bio_external_result.dict() if isinstance(bio_external_result, ValidationResult) else bio_external_result
        
        return {
            "bio_local": bio_local_result,
            "bio_external": bio_external_result
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
        bio_local_result = await self.bio_rules.validate(df, metadata.experiment_type or 'guide_rna')
        report["stages"]["bio_local"] = bio_local_result.dict()
        
        # External lookups second (slower)
        bio_external_result = await self.bio_lookups.validate(df, 'gene_symbols')
        report["stages"]["bio_external"] = bio_external_result.dict()
        
        return {
            "bio_local": bio_local_result,
            "bio_external": bio_external_result
        }
    
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
            "issues": [{"message": str(error), "severity": "error"}],
            "execution_time_ms": 0,
            "records_processed": 0
        }