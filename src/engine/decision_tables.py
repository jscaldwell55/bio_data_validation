# src/engine/decision_tables.py
"""
Decision tables for policy engine.
Provides programmatic access to decision logic.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Issue severity levels"""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Decision(str, Enum):
    """Validation decisions"""
    ACCEPTED = "ACCEPTED"
    CONDITIONAL_ACCEPT = "CONDITIONAL_ACCEPT"
    REJECTED = "REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"


@dataclass
class DecisionRule:
    """Single decision rule"""
    id: str
    name: str
    condition: str
    decision: Decision
    priority: int
    description: str


@dataclass
class ThresholdConfig:
    """Threshold configuration"""
    critical_threshold: int = 1
    error_threshold: int = 5
    warning_threshold: int = 10
    moderate_warning_threshold: int = 3


@dataclass
class ReviewTrigger:
    """Human review trigger configuration"""
    on_critical: bool = True
    error_count_threshold: int = 3
    warning_count_threshold: int = 15
    confidence_threshold: float = 0.7
    on_novel_errors: bool = True


class DecisionTable:
    """
    Decision table implementation for policy-based decisions.
    Maps severity counts to validation decisions.
    """
    
    # Default decision rules (priority order)
    DEFAULT_RULES = [
        DecisionRule(
            id="RULE_001",
            name="Reject on Critical",
            condition="severity.critical >= threshold.critical_threshold",
            decision=Decision.REJECTED,
            priority=1,
            description="Any critical issues result in rejection"
        ),
        DecisionRule(
            id="RULE_002",
            name="Reject on High Errors",
            condition="severity.error >= threshold.error_threshold",
            decision=Decision.REJECTED,
            priority=2,
            description="High error count indicates systemic issues"
        ),
        DecisionRule(
            id="RULE_003",
            name="Conditional Accept on High Warnings",
            condition="severity.warning >= threshold.warning_threshold",
            decision=Decision.CONDITIONAL_ACCEPT,
            priority=3,
            description="Many warnings suggest data may need review"
        ),
        DecisionRule(
            id="RULE_004",
            name="Conditional Accept on Moderate Warnings",
            condition="severity.warning >= threshold.moderate_warning_threshold AND severity.error == 0",
            decision=Decision.CONDITIONAL_ACCEPT,
            priority=4,
            description="Some warnings present but no errors"
        ),
        DecisionRule(
            id="RULE_005",
            name="Accept Clean Data",
            condition="severity.error == 0 AND severity.warning < threshold.moderate_warning_threshold",
            decision=Decision.ACCEPTED,
            priority=5,
            description="Minimal or no issues detected"
        )
    ]
    
    def __init__(
        self,
        thresholds: Optional[ThresholdConfig] = None,
        review_triggers: Optional[ReviewTrigger] = None,
        custom_rules: Optional[List[DecisionRule]] = None
    ):
        self.thresholds = thresholds or ThresholdConfig()
        self.review_triggers = review_triggers or ReviewTrigger()
        self.rules = custom_rules or self.DEFAULT_RULES
        # Sort rules by priority
        self.rules.sort(key=lambda r: r.priority)
    
    def make_decision(self, severity_counts: Dict[str, int]) -> Decision:
        """
        Make decision based on severity counts.
        
        Args:
            severity_counts: Dict with keys: critical, error, warning, info
            
        Returns:
            Decision enum value
        """
        # Check each rule in priority order
        for rule in self.rules:
            if self._evaluate_condition(rule.condition, severity_counts):
                return rule.decision
        
        # Default to ACCEPTED if no rules match
        return Decision.ACCEPTED
    
    def check_review_trigger(
        self,
        severity_counts: Dict[str, int],
        confidence_scores: Optional[List[float]] = None,
        has_novel_errors: bool = False
    ) -> bool:
        """
        Check if human review should be triggered.
        
        Args:
            severity_counts: Dict with issue counts by severity
            confidence_scores: Optional list of confidence scores
            has_novel_errors: Whether novel error patterns detected
            
        Returns:
            True if human review should be triggered
        """
        triggers = self.review_triggers
        
        # Always trigger on critical
        if triggers.on_critical and severity_counts.get("critical", 0) > 0:
            return True
        
        # Trigger on error threshold
        if severity_counts.get("error", 0) >= triggers.error_count_threshold:
            return True
        
        # Trigger on warning threshold
        if severity_counts.get("warning", 0) >= triggers.warning_count_threshold:
            return True
        
        # Trigger on low confidence
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            if avg_confidence < triggers.confidence_threshold:
                return True
        
        # Trigger on novel errors
        if triggers.on_novel_errors and has_novel_errors:
            return True
        
        return False
    
    def _evaluate_condition(self, condition: str, severity_counts: Dict[str, int]) -> bool:
        """
        Evaluate a condition string against severity counts.
        
        Args:
            condition: Condition string (e.g., "severity.critical >= 1")
            severity_counts: Current severity counts
            
        Returns:
            True if condition is met
        """
        # Create evaluation context
        context = {
            "severity": severity_counts,
            "threshold": self.thresholds
        }
        
        try:
            # Safely evaluate condition
            # Replace readable names with dict access
            eval_str = condition
            eval_str = eval_str.replace("severity.critical", "context['severity'].get('critical', 0)")
            eval_str = eval_str.replace("severity.error", "context['severity'].get('error', 0)")
            eval_str = eval_str.replace("severity.warning", "context['severity'].get('warning', 0)")
            eval_str = eval_str.replace("threshold.critical_threshold", "context['threshold'].critical_threshold")
            eval_str = eval_str.replace("threshold.error_threshold", "context['threshold'].error_threshold")
            eval_str = eval_str.replace("threshold.warning_threshold", "context['threshold'].warning_threshold")
            eval_str = eval_str.replace("threshold.moderate_warning_threshold", "context['threshold'].moderate_warning_threshold")
            
            return eval(eval_str, {"__builtins__": {}}, context)
        except Exception as e:
            # Log error and return False on evaluation failure
            import logging
            logging.error(f"Failed to evaluate condition '{condition}': {str(e)}")
            return False
    
    def get_rationale(
        self,
        decision: Decision,
        severity_counts: Dict[str, int]
    ) -> str:
        """
        Generate human-readable rationale for decision.
        
        Args:
            decision: The decision made
            severity_counts: Severity counts
            
        Returns:
            Rationale string
        """
        parts = []
        
        if severity_counts.get("critical", 0) > 0:
            parts.append(f"{severity_counts['critical']} critical issue(s)")
        
        if severity_counts.get("error", 0) > 0:
            parts.append(f"{severity_counts['error']} error(s)")
        
        if severity_counts.get("warning", 0) > 0:
            parts.append(f"{severity_counts['warning']} warning(s)")
        
        if not parts:
            return "All validation checks passed"
        
        issues_str = ", ".join(parts)
        
        if decision == Decision.REJECTED:
            return f"Dataset rejected due to: {issues_str}"
        elif decision == Decision.CONDITIONAL_ACCEPT:
            return f"Dataset conditionally accepted with: {issues_str}"
        elif decision == Decision.ACCEPTED:
            return f"Dataset accepted with: {issues_str}"
        else:
            return f"Dataset requires review: {issues_str}"


# Pre-configured decision tables for common use cases
class DecisionTablePresets:
    """Pre-configured decision tables"""
    
    @staticmethod
    def strict() -> DecisionTable:
        """Strict validation - reject on any errors"""
        return DecisionTable(
            thresholds=ThresholdConfig(
                critical_threshold=1,
                error_threshold=1,
                warning_threshold=5
            )
        )
    
    @staticmethod
    def lenient() -> DecisionTable:
        """Lenient validation - accept with warnings"""
        return DecisionTable(
            thresholds=ThresholdConfig(
                critical_threshold=1,
                error_threshold=10,
                warning_threshold=20
            )
        )
    
    @staticmethod
    def production() -> DecisionTable:
        """Production-ready validation settings"""
        return DecisionTable(
            thresholds=ThresholdConfig(
                critical_threshold=1,
                error_threshold=5,
                warning_threshold=10
            ),
            review_triggers=ReviewTrigger(
                on_critical=True,
                error_count_threshold=3,
                warning_count_threshold=15,
                confidence_threshold=0.7
            )
        )