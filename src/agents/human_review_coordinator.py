# src/agents/human_review_coordinator.py
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
import asyncio

from src.schemas.base_schemas import ValidationIssue, ValidationSeverity, ReviewPriority, ReviewStatus

logger = logging.getLogger(__name__)


def _issue_to_dict(issue: Any) -> Dict[str, Any]:
    """
    Convert issue to dict regardless of input type.

    Handles Pydantic models, dicts, and objects with attributes.
    """
    if isinstance(issue, dict):
        return issue
    elif hasattr(issue, 'model_dump'):
        return issue.model_dump()
    elif hasattr(issue, 'dict'):
        return issue.dict()
    else:
        # Fallback: try to access as object attributes
        return {
            'field': getattr(issue, 'field', 'unknown'),
            'message': getattr(issue, 'message', ''),
            'severity': getattr(issue, 'severity', 'info'),
            'rule_id': getattr(issue, 'rule_id', None),
            'metadata': getattr(issue, 'metadata', {})
        }


class HumanReviewConfig:
    """Configuration for human review coordinator"""
    def __init__(self):
        self.error_threshold = 3
        self.warning_threshold = 15
        self.uncertainty_threshold = 0.6
        self.novelty_threshold = 0.8


class HumanReviewCoordinator:
    """
    Agent that coordinates human-in-the-loop review process.
    Uses active learning to prioritize and route issues to human experts.
    This is a genuine agent - it learns and adapts based on human feedback.
    """
    
    def __init__(self, config: Optional[HumanReviewConfig] = None):
        self.config = config or HumanReviewConfig()
        self.logger = logging.getLogger("human_review_coordinator")
        self.feedback_history: List[Dict] = []
        self.learned_patterns: Dict[str, Any] = {}
        
        # Active learning parameters
        self.uncertainty_threshold = self.config.uncertainty_threshold
        self.novelty_threshold = self.config.novelty_threshold
        
        self.logger.info("HumanReviewCoordinator initialized")
    
    # FIXED: Add missing test methods
    def should_trigger_review(self, report: Dict[str, Any]) -> bool:
        """Check if human review should be triggered"""
        severity_counts = self._count_severities_from_report(report)
        
        # Trigger on critical
        if severity_counts.get("critical", 0) > 0:
            return True
        
        # Trigger on error threshold
        if severity_counts.get("error", 0) >= self.config.error_threshold:
            return True
        
        # Trigger on warning threshold
        if severity_counts.get("warning", 0) >= self.config.warning_threshold:
            return True
        
        return False
    
    def prioritize_issues(self, issues: List[ValidationIssue]) -> List[ValidationIssue]:
        """Prioritize issues for review"""
        issue_list = []
        for issue in issues:
            issue_dict = _issue_to_dict(issue)
            issue_dict["priority"] = self._calculate_priority(issue_dict)
            issue_list.append(issue_dict)

        issue_list.sort(key=lambda x: self._priority_score(x.get("priority", ReviewPriority.LOW)), reverse=True)
        return issue_list
    
    def route_to_expert(self, issues: List[ValidationIssue]) -> str:
        """Route to appropriate expert"""
        issue_dicts = [_issue_to_dict(i) for i in issues]
        return self._route_to_reviewer(issue_dicts)
    
    def capture_feedback(self, review_id: str, feedback: Dict[str, Any]):
        """Capture human feedback"""
        self.feedback_history.append({
            "review_id": review_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback": feedback
        })
        self._learn_from_feedback(feedback)
    
    def update_learned_patterns(self, pattern: str, feedback: Dict[str, Any]):
        """Update learned patterns from feedback"""
        if pattern not in self.learned_patterns:
            self.learned_patterns[pattern] = {
                "seen_count": 0,
                "feedback_count": 0,
                "decisions": [],
                "consistency": 0.0
            }
        
        self.learned_patterns[pattern]["feedback_count"] += 1
        if "decision" in feedback:
            self.learned_patterns[pattern]["decisions"].append(feedback["decision"])
    
    def create_review_task(self, validation_report: Dict[str, Any], priority: ReviewPriority) -> Dict[str, Any]:
        """Create a review task"""
        return {
            "review_id": f"review_{validation_report.get('validation_id', 'unknown')}",
            "validation_id": validation_report.get("validation_id"),
            "priority": priority.value if isinstance(priority, ReviewPriority) else priority,
            "status": ReviewStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "issues": self._extract_issues_from_report(validation_report)
        }
    
    def get_review_metrics(self) -> Dict[str, Any]:
        """Get review metrics"""
        return {
            "total_reviews": len(self.feedback_history),
            "learned_patterns": len(self.learned_patterns),
            "feedback_count": len(self.feedback_history)
        }
    
    def track_expert_performance(self, expert_id: str) -> Dict[str, Any]:
        """Track expert performance"""
        expert_reviews = [f for f in self.feedback_history if f.get("reviewer_id") == expert_id]
        return {
            "expert_id": expert_id,
            "total_reviews": len(expert_reviews),
            "average_time": 0.0  # Would calculate from actual data
        }
    
    def try_auto_resolve(self, issue: ValidationIssue) -> Optional[str]:
        """Try to auto-resolve issue based on learned patterns"""
        issue_dict = _issue_to_dict(issue)
        signature = self._get_issue_signature(issue_dict)
        
        if signature in self.learned_patterns:
            pattern = self.learned_patterns[signature]
            if pattern["consistency"] > 0.8 and pattern["feedback_count"] > 5:
                # High confidence auto-resolution
                most_common = max(set(pattern["decisions"]), key=pattern["decisions"].count)
                return most_common
        
        return None
    
    def auto_resolve_issues(self, issues: List[ValidationIssue]) -> List[ValidationIssue]:
        """Auto-resolve issues where possible"""
        unresolved = []
        for issue in issues:
            if self.try_auto_resolve(issue) is None:
                unresolved.append(issue)
        return unresolved
    
    async def coordinate_review(
        self,
        validation_report: Dict[str, Any],
        dataset: Any
    ) -> Dict[str, Any]:
        """
        Coordinate human review process with active learning.
        
        Args:
            validation_report: Complete validation report
            dataset: Original dataset for context
            
        Returns:
            Review result with human decision and feedback
        """
        start_time = time.time()
        
        # Prioritize issues for review
        prioritized_issues = self._prioritize_issues(validation_report)
        
        # Select most informative issues using active learning
        selected_issues = self._select_informative_issues(prioritized_issues)
        
        # Create review package
        review_package = self._create_review_package(
            validation_report,
            selected_issues,
            dataset
        )
        
        # Route to appropriate reviewer
        reviewer_id = self._route_to_reviewer(selected_issues)
        
        # In production, this would integrate with actual review UI
        # For now, we'll simulate the review process
        review_result = await self._simulate_review(review_package, reviewer_id)
        
        # Learn from feedback
        self._learn_from_feedback(review_result)
        
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "status": "completed",
            "decision": review_result["decision"],
            "reviewer_id": reviewer_id,
            "reviewed_issues": len(selected_issues),
            "total_issues": len(prioritized_issues),
            "execution_time_ms": execution_time,
            "feedback": review_result.get("feedback", {}),
            "learned_patterns": len(self.learned_patterns)
        }
    
    def _count_severities_from_report(self, report: Dict[str, Any]) -> Dict[str, int]:
        """Count severities from report"""
        counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        for stage_data in report.get("stages", {}).values():
            for issue in stage_data.get("issues", []):
                sev = issue.get("severity", "info")
                counts[sev] = counts.get(sev, 0) + 1
        return counts
    
    def _extract_issues_from_report(self, report: Dict[str, Any]) -> List[Dict]:
        """Extract all issues from report"""
        issues = []
        for stage_data in report.get("stages", {}).values():
            issues.extend(stage_data.get("issues", []))
        return issues
    
    def _prioritize_issues(
        self,
        validation_report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Prioritize issues for human review"""
        all_issues = []

        # Collect all issues from all stages
        for stage_name, stage_data in validation_report.get("stages", {}).items():
            issues = stage_data.get("issues", [])
            for issue in issues:
                issue_dict = _issue_to_dict(issue)
                issue_dict["stage"] = stage_name
                issue_dict["priority"] = self._calculate_priority(issue_dict)
                all_issues.append(issue_dict)

        # Sort by priority
        all_issues.sort(key=lambda x: self._priority_score(x["priority"]), reverse=True)

        return all_issues
    
    def _calculate_priority(self, issue: Dict[str, Any]) -> ReviewPriority:
        """Calculate review priority for an issue"""
        severity = issue.get("severity", "info")
        
        if severity == "critical":
            return ReviewPriority.CRITICAL
        elif severity == "error":
            # Check if error is novel
            if self._is_novel_error(issue):
                return ReviewPriority.CRITICAL
            return ReviewPriority.HIGH
        elif severity == "warning":
            return ReviewPriority.MEDIUM
        else:
            return ReviewPriority.LOW
    
    def _select_informative_issues(
        self,
        prioritized_issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Use active learning to select most informative issues.
        Focuses on uncertain and novel cases.
        """
        selected = []
        
        for issue in prioritized_issues:
            # Always include critical issues
            if issue["priority"] == ReviewPriority.CRITICAL:
                selected.append(issue)
                continue
            
            # Calculate informativeness score
            uncertainty_score = self._calculate_uncertainty(issue)
            novelty_score = self._calculate_novelty(issue)
            
            informativeness = 0.6 * uncertainty_score + 0.4 * novelty_score
            
            # Select if above threshold or high priority
            if (informativeness > self.uncertainty_threshold or 
                issue["priority"] == ReviewPriority.HIGH):
                selected.append(issue)
            
            # Limit total issues to avoid overwhelming reviewer
            if len(selected) >= 20:
                break
        
        return selected
    
    def _calculate_uncertainty(self, issue: Dict[str, Any]) -> float:
        """Calculate uncertainty score for an issue"""
        # Check if we've seen similar issues before
        issue_signature = self._get_issue_signature(issue)
        
        if issue_signature not in self.learned_patterns:
            return 1.0  # Maximum uncertainty for new patterns
        
        pattern = self.learned_patterns[issue_signature]
        
        # Lower uncertainty if we have consistent feedback
        feedback_count = pattern.get("feedback_count", 0)
        consistency = pattern.get("consistency", 0.5)
        
        if feedback_count > 5 and consistency > 0.8:
            return 0.2  # Low uncertainty
        elif feedback_count > 2:
            return 0.5  # Medium uncertainty
        else:
            return 0.8  # High uncertainty
    
    def _calculate_novelty(self, issue: Dict[str, Any]) -> float:
        """Calculate novelty score for an issue"""
        issue_signature = self._get_issue_signature(issue)
        
        if issue_signature not in self.learned_patterns:
            return 1.0  # Completely novel
        
        pattern = self.learned_patterns[issue_signature]
        seen_count = pattern.get("seen_count", 0)
        
        # Novelty decreases with frequency
        if seen_count > 100:
            return 0.1
        elif seen_count > 50:
            return 0.3
        elif seen_count > 10:
            return 0.5
        else:
            return 0.7
    
    def _is_novel_error(self, issue: Dict[str, Any]) -> bool:
        """Check if error pattern is novel"""
        issue_signature = self._get_issue_signature(issue)
        return issue_signature not in self.learned_patterns
    
    def _get_issue_signature(self, issue: Dict[str, Any]) -> str:
        """Generate signature for issue pattern matching"""
        rule_id = issue.get("rule_id", "")
        field = issue.get("field", "")
        severity = issue.get("severity", "")
        
        # Create normalized signature
        return f"{rule_id}:{field}:{severity}"
    
    def _create_review_package(
        self,
        validation_report: Dict[str, Any],
        selected_issues: List[Dict[str, Any]],
        dataset: Any
    ) -> Dict[str, Any]:
        """Create comprehensive package for human reviewer"""
        return {
            "dataset_id": validation_report.get("dataset_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_issues": len(selected_issues),
                "critical_count": sum(1 for i in selected_issues if i.get("priority") == ReviewPriority.CRITICAL),
                "high_count": sum(1 for i in selected_issues if i.get("priority") == ReviewPriority.HIGH),
            },
            "issues": selected_issues,
            "context": {
                "dataset_metadata": validation_report.get("metadata", {}),
                "validation_stages": list(validation_report.get("stages", {}).keys()),
            },
            "sample_data": self._extract_sample_data(dataset, selected_issues),
            "recommendations": self._generate_recommendations(selected_issues)
        }
    
    def _route_to_reviewer(self, issues: List[Dict[str, Any]]) -> str:
        """Route review to appropriate expert based on issue types"""
        # Analyze issue types
        bio_issues = sum(1 for i in issues if i.get("stage") in ["bio_rules", "bio_lookups", "bio_local", "bio_external"])
        schema_issues = sum(1 for i in issues if i.get("stage") == "schema")
        rule_issues = sum(1 for i in issues if i.get("stage") == "rules")
        
        # Route based on predominant issue type
        if bio_issues > schema_issues and bio_issues > rule_issues:
            return "biologist_expert"
        elif schema_issues > rule_issues:
            return "data_engineer"
        else:
            return "quality_specialist"
    
    async def _simulate_review(
        self,
        review_package: Dict[str, Any],
        reviewer_id: str
    ) -> Dict[str, Any]:
        """
        Simulate human review process.
        In production, this would integrate with actual review UI.
        """
        # Simulate review time
        await asyncio.sleep(0.1)
        
        # Simulated decision based on issue severity
        critical_count = review_package["summary"]["critical_count"]
        high_count = review_package["summary"]["high_count"]
        
        if critical_count > 0:
            decision = "REJECTED"
            feedback_type = "critical_issues_found"
        elif high_count > 5:
            decision = "REJECTED"
            feedback_type = "too_many_high_priority_issues"
        elif high_count > 0:
            decision = "CONDITIONAL_ACCEPT"
            feedback_type = "acceptable_with_corrections"
        else:
            decision = "ACCEPTED"
            feedback_type = "minor_issues_acceptable"
        
        return {
            "decision": decision,
            "reviewer_id": reviewer_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback": {
                "type": feedback_type,
                "comments": f"Reviewed {len(review_package['issues'])} issues",
                "corrected_issues": []  # Would contain human corrections
            }
        }
    
    def _learn_from_feedback(self, review_result: Dict[str, Any]):
        """
        Learn from human feedback to improve future routing and prioritization.
        Implements RLHF-style learning.
        """
        self.feedback_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": review_result.get("decision"),
            "reviewer_id": review_result.get("reviewer_id"),
            "feedback": review_result.get("feedback", {})
        })
        
        # Update learned patterns
        feedback = review_result.get("feedback", {})
        for issue in feedback.get("corrected_issues", []):
            signature = self._get_issue_signature(issue)
            
            if signature not in self.learned_patterns:
                self.learned_patterns[signature] = {
                    "seen_count": 0,
                    "feedback_count": 0,
                    "decisions": [],
                    "consistency": 0.0
                }
            
            pattern = self.learned_patterns[signature]
            pattern["seen_count"] += 1
            pattern["feedback_count"] += 1
            pattern["decisions"].append(review_result.get("decision"))
            
            # Calculate consistency
            if len(pattern["decisions"]) > 1:
                most_common = max(set(pattern["decisions"]), key=pattern["decisions"].count)
                pattern["consistency"] = pattern["decisions"].count(most_common) / len(pattern["decisions"])
        
        self.logger.info(f"Learned from feedback. Total patterns: {len(self.learned_patterns)}")
    
    def _extract_sample_data(
        self,
        dataset: Any,
        issues: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract relevant sample data for review context"""
        # Extract up to 5 examples for each issue
        samples = []
        for issue in issues[:5]:  # Limit to first 5 issues
            samples.append({
                "issue": issue.get("message"),
                "field": issue.get("field"),
                "example": "Sample data would be extracted here"
            })
        return samples
    
    def _generate_recommendations(
        self,
        issues: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations for reviewer"""
        recommendations = []
        
        # Analyze issue patterns
        field_counts = {}
        for issue in issues:
            field = issue.get("field", "unknown")
            field_counts[field] = field_counts.get(field, 0) + 1
        
        # Generate recommendations
        for field, count in sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            if count > 1:
                recommendations.append(
                    f"Review all {count} issues related to field '{field}' - may indicate systematic problem"
                )
        
        return recommendations
    
    @staticmethod
    def _priority_score(priority: ReviewPriority) -> int:
        """Convert priority to numeric score for sorting"""
        if isinstance(priority, str):
            priority = ReviewPriority(priority)
        scores = {
            ReviewPriority.CRITICAL: 4,
            ReviewPriority.HIGH: 3,
            ReviewPriority.MEDIUM: 2,
            ReviewPriority.LOW: 1
        }
        return scores.get(priority, 0)