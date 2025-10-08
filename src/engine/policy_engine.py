# src/engine/policy_engine.py
"""
Policy-based decision engine for validation outcomes.
Uses configuration-driven rules to make accept/reject decisions.
"""
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

from src.schemas.base_schemas import (
    ConfigurableComponent,
    Decision,
    ValidationSeverity,
    serialize_for_json
)

logger = logging.getLogger(__name__)


class PolicyEngine(ConfigurableComponent):
    """
    Makes validation decisions based on configured policies.
    Uses table-driven decision logic for transparency and maintainability.
    """
    
    def __init__(
        self,
        config: Optional[Union[str, Path, Dict[str, Any]]] = None,
        config_path: Optional[Union[str, Path]] = None,
        strict: bool = False,
        **kwargs
    ):
        """
        Initialize with policy configuration.

        Args:
            config: Can be:
                - str/Path: Path to policy YAML file
                - dict: Configuration dictionary (for testing)
                - None: Use default configuration
            config_path: Alias for config (for backward compatibility)
            strict: If True, raise YAMLError for malformed YAML
            **kwargs: Override specific config values
        """
        # Support config_path as alias for config
        if config_path is not None and config is None:
            config = config_path

        # Call parent __init__ first to load config
        super().__init__(config, strict=strict, **kwargs)
        
        # Extract policy components from loaded config
        self.decision_matrix = self.config.get('decision_matrix', {})
        self.review_triggers = self.config.get('human_review_triggers', {})
        
        logger.info("PolicyEngine initialized with decision matrix")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default policy configuration."""
        return {
            'decision_matrix': {
                'critical_threshold': 1,           # Any critical issue = reject
                'error_threshold': 5,              # 5+ errors = reject
                'warning_threshold': 10,           # 10+ warnings = conditional
                'moderate_warning_threshold': 5    # FIXED: 5+ warnings = conditional (was 3)
            },
            'human_review_triggers': {
                'on_critical': True,
                'error_count_threshold': 3,
                'warning_count_threshold': 15
            }
        }
    
    def make_decision(self, validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make final validation decision based on policy rules.

        Args:
            validation_report: Complete validation report with all stages

        Returns:
            Dictionary with decision, rationale, and review requirement
            {
                'decision': str (lowercase: 'accepted', 'conditional_accept', 'rejected'),
                'rationale': str,
                'requires_review': bool,
                'severity_counts': dict
            }
        """
        # Count issues by severity across all stages
        severity_counts = self._count_severities(validation_report)

        # Apply decision matrix - returns Decision enum
        decision_enum = self._apply_decision_matrix(severity_counts)

        # Determine if human review is required
        requires_review = self._should_trigger_review(severity_counts)

        # Generate rationale
        rationale = self._generate_rationale(decision_enum, severity_counts)

        # Always return decision as lowercase string
        result = {
            'decision': decision_enum.value.lower(),
            'rationale': rationale,
            'requires_review': requires_review,
            'severity_counts': severity_counts
        }

        # Add conditions for CONDITIONAL_ACCEPT
        if decision_enum == Decision.CONDITIONAL_ACCEPT:
            result['conditions'] = self._generate_conditions(severity_counts, validation_report)

        return result
    
    def _count_severities(self, report: Dict[str, Any]) -> Dict[str, int]:
        """
        Count issues by severity across all validation stages.
        
        FIXED: Only count ERROR, WARNING, and CRITICAL - not INFO.
        INFO-level issues are informational and shouldn't affect decisions.
        """
        counts = {
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0
        }
        
        for stage_name, stage_data in report.get('stages', {}).items():
            if isinstance(stage_data, dict):
                issues = stage_data.get('issues', [])
                for issue in issues:
                    # Handle both dict and object forms
                    if isinstance(issue, dict):
                        severity = issue.get('severity', 'info')
                    else:
                        severity = getattr(issue, 'severity', 'info')
                    
                    # Normalize severity to lowercase string
                    if hasattr(severity, 'value'):
                        severity = severity.value
                    
                    severity_key = str(severity).lower()
                    if severity_key in counts:
                        counts[severity_key] += 1
        
        return counts
    
    def _apply_decision_matrix(self, severity_counts: Dict[str, int]) -> Decision:
        """
        Apply decision matrix rules to determine outcome.
    
        Decision Rules (FIXED for better thresholds):
        1. Any critical issue → REJECTED
        2. 5+ errors → REJECTED  
        3. 1-4 errors → CONDITIONAL_ACCEPT
        4. 5+ warnings (no errors) → CONDITIONAL_ACCEPT (was 3+)
        5. 0 errors, 0-4 warnings → ACCEPTED (was 0-2)
        
        Rationale: Perfect datasets with 1-2 warnings (e.g., suboptimal guide length)
        should still be ACCEPTED. Warnings are advisory, not blocking.
        """
        critical_threshold = self.decision_matrix.get('critical_threshold', 1)
        error_threshold = self.decision_matrix.get('error_threshold', 5)
        moderate_warning_threshold = self.decision_matrix.get('moderate_warning_threshold', 5)  # FIXED: Default 5

        # Rule 1: Any critical issue = REJECTED
        if severity_counts['critical'] >= critical_threshold:
            return Decision.REJECTED

        # Rule 2: Too many errors (>=5) = REJECTED
        if severity_counts['error'] >= error_threshold:
            return Decision.REJECTED

        # Rule 3: Any errors (1-4) = CONDITIONAL_ACCEPT
        if severity_counts['error'] > 0:
            return Decision.CONDITIONAL_ACCEPT

        # Rule 4: FIXED - Many warnings (>=5, no errors) = CONDITIONAL_ACCEPT
        # This allows 1-4 warnings to still result in ACCEPTED
        if severity_counts['warning'] >= moderate_warning_threshold:
            return Decision.CONDITIONAL_ACCEPT

        # Rule 5: Few/no warnings (0-4), no errors = ACCEPTED
        return Decision.ACCEPTED
    
    def _should_trigger_review(self, severity_counts: Dict[str, int]) -> bool:
        """Determine if human review should be triggered."""
        # Trigger on critical issues
        if self.review_triggers.get('on_critical', True) and severity_counts['critical'] > 0:
            return True
        
        # Trigger on error threshold
        error_threshold = self.review_triggers.get('error_count_threshold', 3)
        if severity_counts['error'] >= error_threshold:
            return True
        
        # Trigger on warning threshold
        warning_threshold = self.review_triggers.get('warning_count_threshold', 15)
        if severity_counts['warning'] >= warning_threshold:
            return True
        
        return False
    
    def _generate_rationale(self, decision: Decision, severity_counts: Dict[str, int]) -> str:
        """Generate human-readable decision rationale."""
        # Handle both Decision enum and string input
        if isinstance(decision, str):
            decision = Decision(decision)
        
        parts = []
        
        if decision == Decision.REJECTED:
            if severity_counts['critical'] > 0:
                parts.append(f"{severity_counts['critical']} critical issue(s)")
            if severity_counts['error'] >= self.decision_matrix.get('error_threshold', 5):
                parts.append(f"{severity_counts['error']} errors exceed threshold")
            rationale = f"Rejected: {', '.join(parts) if parts else 'validation failed'}"
        
        elif decision == Decision.CONDITIONAL_ACCEPT:
            if severity_counts['error'] > 0:
                parts.append(f"{severity_counts['error']} error(s)")
            if severity_counts['warning'] > 0:
                parts.append(f"{severity_counts['warning']} warning(s)")
            rationale = f"Conditional accept: {', '.join(parts)} require attention"
        
        else:  # ACCEPTED
            if severity_counts['warning'] > 0:
                rationale = f"Accepted with {severity_counts['warning']} warning(s)"
            else:
                rationale = "All validation checks passed"

        return rationale

    def _generate_conditions(
        self,
        severity_counts: Dict[str, int],
        validation_report: Dict[str, Any]
    ) -> list:
        """Generate conditions/recommendations for CONDITIONAL_ACCEPT decisions."""
        conditions = []

        if severity_counts['error'] > 0:
            conditions.append(f"Review and address {severity_counts['error']} error(s) before production use")

        if severity_counts['warning'] > 0:
            conditions.append(f"Consider reviewing {severity_counts['warning']} warning(s) for optimization")

        # Add specific recommendations based on issues
        for stage_name, stage_data in validation_report.get('stages', {}).items():
            if isinstance(stage_data, dict):
                issues = stage_data.get('issues', [])
                if issues:
                    conditions.append(f"Review {stage_name} validation issues")

        return conditions if conditions else ["Manual review recommended before proceeding"]

    def count_issues_by_severity(self, report: Dict[str, Any]) -> Dict[ValidationSeverity, int]:
        """
        Public method to count issues by severity across all validation stages.

        Args:
            report: Validation report with stages

        Returns:
            Dict mapping ValidationSeverity enum to count
        """
        string_counts = self._count_severities(report)

        # Convert string keys to enum keys
        return {
            ValidationSeverity.CRITICAL: string_counts.get('critical', 0),
            ValidationSeverity.ERROR: string_counts.get('error', 0),
            ValidationSeverity.WARNING: string_counts.get('warning', 0),
            ValidationSeverity.INFO: string_counts.get('info', 0)
        }