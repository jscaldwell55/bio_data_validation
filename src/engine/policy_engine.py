# src/engine/policy_engine.py
import yaml
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PolicyEngine:
    """
    Table-driven decision engine for validation outcomes.
    Uses YAML-based policy configuration or dict config.
    """
    
    def __init__(
        self, 
        config_path: Optional[Union[str, Path]] = None, 
        config: Optional[Dict] = None,
        strict: bool = False
    ):
        """
        Initialize policy engine from YAML configuration or dict.
        
        Args:
            config_path: Path to policy configuration YAML (optional)
            config: Configuration dict (optional, takes precedence over config_path)
            strict: If True, raise errors instead of using defaults
        """
        if config is not None:
            # Use provided config dict
            self.config = config
        elif config_path is not None:
            # Load from YAML file
            try:
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
            except FileNotFoundError:
                if strict:
                    raise
                logger.warning(f"Config file not found: {config_path}, using defaults")
                self.config = self._get_default_config()
            except yaml.YAMLError as e:
                if strict:
                    raise
                logger.error(f"Invalid YAML in {config_path}: {e}, using defaults")
                self.config = self._get_default_config()
        else:
            # Use default configuration
            self.config = self._get_default_config()
        
        self.policies = self.config.get('policies', [])
        self.decision_matrix = self.config.get('decision_matrix', {})
        self.human_review_triggers = self.config.get('human_review_triggers', {})
        
        logger.info(f"Loaded {len(self.policies)} policy rules")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'policies': [],
            'decision_matrix': {
                'critical_threshold': 1,
                'error_threshold': 5,
                'warning_threshold': 10,
                'moderate_warning_threshold': 3
            },
            'human_review_triggers': {
                'on_critical': True,
                'error_count_threshold': 3,
                'warning_count_threshold': 15,
                'confidence_threshold': 0.7,
                'on_novel_errors': True
            }
        }
    
    def make_decision(self, validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make final decision based on validation results and policy rules.
        
        Args:
            validation_report: Complete validation report
            
        Returns:
            Decision dict with decision, rationale, and review flag
        """
        # Collect severity counts
        severity_counts = self._count_severities(validation_report)
        
        # Check if human review is required
        requires_review = self._check_human_review_triggers(
            validation_report,
            severity_counts
        )
        
        # Apply decision matrix
        decision = self._apply_decision_matrix(severity_counts)
        
        # Generate rationale
        rationale = self._generate_rationale(severity_counts, decision)
        
        return {
            "decision": decision,
            "rationale": rationale,
            "requires_review": requires_review,
            "severity_counts": severity_counts
        }
    
    def count_issues_by_severity(self, validation_report: Dict[str, Any]) -> Dict[str, int]:
        """
        Public method to count issues by severity.
        
        Args:
            validation_report: Complete validation report
            
        Returns:
            Dict with counts by severity level
        """
        return self._count_severities(validation_report)
    
    def _count_severities(self, report: Dict[str, Any]) -> Dict[str, int]:
        """Count issues by severity across all stages"""
        counts = {
            "critical": 0,
            "error": 0,
            "warning": 0,
            "info": 0
        }
        
        stages = report.get("stages", {})
        if not stages:
            logger.warning("Report has no stages")
            return counts
        
        for stage_name, stage_data in stages.items():
            if not isinstance(stage_data, dict):
                logger.warning(f"Stage {stage_name} is not a dict: {type(stage_data)}")
                continue
            
            issues = stage_data.get("issues", [])
            for issue in issues:
                # Handle both Pydantic objects and dicts
                if hasattr(issue, 'severity'):
                    severity_value = issue.severity
                elif isinstance(issue, dict):
                    severity_value = issue.get("severity", "info")
                else:
                    logger.warning(f"Unknown issue type: {type(issue)}")
                    continue
                
                # Convert enum to string if needed
                if hasattr(severity_value, 'value'):
                    severity_value = severity_value.value
                
                # Normalize to lowercase string
                severity_str = str(severity_value).lower()
                
                if severity_str in counts:
                    counts[severity_str] += 1
        
        return counts
    
    def _apply_decision_matrix(self, severity_counts: Dict[str, int]) -> str:
        """Apply decision matrix rules"""
        # Check critical threshold
        critical_threshold = self.decision_matrix.get("critical_threshold", 1)
        if severity_counts["critical"] >= critical_threshold:
            return "REJECTED"
        
        # Check error threshold
        error_threshold = self.decision_matrix.get("error_threshold", 5)
        if severity_counts["error"] >= error_threshold:
            return "REJECTED"
        
        # Check warning threshold for conditional accept
        warning_threshold = self.decision_matrix.get("warning_threshold", 10)
        if severity_counts["warning"] >= warning_threshold:
            return "CONDITIONAL_ACCEPT"
        
        # Check moderate warnings
        moderate_warning_threshold = self.decision_matrix.get("moderate_warning_threshold", 3)
        if severity_counts["warning"] >= moderate_warning_threshold:
            return "CONDITIONAL_ACCEPT"
        
        # All clear - even 1-2 errors or warnings don't trigger rejection
        return "ACCEPTED"
    
    def _check_human_review_triggers(
        self,
        report: Dict[str, Any],
        severity_counts: Dict[str, int]
    ) -> bool:
        """Check if human review should be triggered"""
        triggers = self.human_review_triggers
        
        # Trigger on any critical issues
        if triggers.get("on_critical", True) and severity_counts["critical"] > 0:
            return True
        
        # Trigger on high error count
        error_review_threshold = triggers.get("error_count_threshold", 3)
        if severity_counts["error"] >= error_review_threshold:
            return True
        
        # Trigger on high warning count
        warning_review_threshold = triggers.get("warning_count_threshold", 15)
        if severity_counts["warning"] >= warning_review_threshold:
            return True
        
        # Trigger on low confidence (if available)
        confidence_threshold = triggers.get("confidence_threshold", 0.7)
        for stage_data in report.get("stages", {}).values():
            if not isinstance(stage_data, dict):
                continue
            confidence = stage_data.get("metadata", {}).get("confidence_score")
            if confidence is not None and confidence < confidence_threshold:
                return True
        
        # Trigger on novel error types
        if triggers.get("on_novel_errors", True):
            for stage_data in report.get("stages", {}).values():
                if not isinstance(stage_data, dict):
                    continue
                for issue in stage_data.get("issues", []):
                    if isinstance(issue, dict):
                        if issue.get("metadata", {}).get("novel", False):
                            return True
        
        return False
    
    def _generate_rationale(
        self,
        severity_counts: Dict[str, int],
        decision: str
    ) -> str:
        """Generate human-readable rationale for decision"""
        parts = []
        
        if severity_counts["critical"] > 0:
            parts.append(f"{severity_counts['critical']} critical issue(s)")
        
        if severity_counts["error"] > 0:
            parts.append(f"{severity_counts['error']} error(s)")
        
        if severity_counts["warning"] > 0:
            parts.append(f"{severity_counts['warning']} warning(s)")
        
        if not parts:
            return "All validation checks passed"
        
        issues_str = ", ".join(parts)
        
        if decision == "REJECTED":
            return f"Dataset rejected due to: {issues_str}"
        elif decision == "CONDITIONAL_ACCEPT":
            return f"Dataset conditionally accepted with: {issues_str}"
        else:
            return f"Dataset accepted with: {issues_str}"