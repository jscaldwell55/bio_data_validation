# src/engine/policy_engine.py
import yaml
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class PolicyEngine:
    """
    Table-driven decision engine for validation outcomes.
    Uses YAML-based policy configuration.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize policy engine from YAML configuration.
        
        Args:
            config_path: Path to policy configuration YAML
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.policies = self.config.get('policies', [])
        self.decision_matrix = self.config.get('decision_matrix', {})
        self.human_review_triggers = self.config.get('human_review_triggers', {})
        
        logger.info(f"Loaded {len(self.policies)} policy rules")
    
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
    
    def _count_severities(self, report: Dict[str, Any]) -> Dict[str, int]:
        """Count issues by severity across all stages"""
        counts = {
            "critical": 0,
            "error": 0,
            "warning": 0,
            "info": 0
        }
        
        for stage_name, stage_data in report.get("stages", {}).items():
            issues = stage_data.get("issues", [])
            for issue in issues:
                severity = issue.get("severity", "info")
                counts[severity] = counts.get(severity, 0) + 1
        
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
        
        # All clear
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
            confidence = stage_data.get("metadata", {}).get("confidence_score")
            if confidence is not None and confidence < confidence_threshold:
                return True
        
        # Trigger on novel error types
        if triggers.get("on_novel_errors", True):
            for stage_data in report.get("stages", {}).values():
                for issue in stage_data.get("issues", []):
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