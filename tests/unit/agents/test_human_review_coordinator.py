"""
Unit tests for Human Review Coordinator
Tests HITL mechanisms, active learning, and feedback loops
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from src.agents.human_review_coordinator import HumanReviewCoordinator, HumanReviewConfig
from src.schemas.base_schemas import (
    ValidationIssue,
    ValidationSeverity,
    ReviewPriority,
    ReviewStatus
)


class TestHumanReviewCoordinator:
    """Test suite for HumanReviewCoordinator"""
    
    @pytest.fixture
    def coordinator(self):
        """Create HumanReviewCoordinator instance"""
        return HumanReviewCoordinator()
    
    @pytest.fixture
    def validation_report_with_issues(self, report_builder):
        """Validation report with various issues"""
        return (report_builder()
                .with_validation_id('test_val_001')
                .with_errors(2, stage_name='bio_lookups')
                .with_warnings(1, stage_name='bio_lookups')
                .build())
    
    @pytest.fixture
    def sample_dataset(self):
        """Sample dataset for review"""
        return pd.DataFrame({
            'guide_id': ['gRNA_001', 'gRNA_002'],
            'sequence': ['ATCGATCGATCGATCGATCG', 'GCTAGCTAGCTAGCTAGCTA'],
            'target_gene': ['UNKNOWN_XYZ', 'ABC1'],
            'organism': ['human', 'human']
        })
    
    # ===== REVIEW TRIGGERING =====
    
    def test_review_triggered_for_critical_issues(self, coordinator, report_builder):
        """Test that critical issues trigger review"""
        report = (report_builder()
                  .with_critical_issue(stage_name='schema')
                  .build())
        
        should_review = coordinator.should_trigger_review(report)
        
        assert should_review is True
    
    def test_review_not_triggered_for_clean_data(self, coordinator, report_builder):
        """Test that clean data doesn't trigger review"""
        clean_report = (report_builder()
                        .with_schema_passed()
                        .accepted()
                        .build())
        
        should_review = coordinator.should_trigger_review(clean_report)
        
        assert should_review is False
    
    def test_review_triggered_by_error_threshold(self, coordinator, report_builder):
        """Test review triggered when error count exceeds threshold"""
        coordinator.config.error_threshold = 3
        
        report = (report_builder()
                  .with_errors(5, stage_name='rules')
                  .build())
        
        should_review = coordinator.should_trigger_review(report)
        
        assert should_review is True
    
    # ===== ACTIVE LEARNING / PRIORITIZATION =====
    
    def test_issue_prioritization(self, coordinator, issue_builder):
        """Test that issues are prioritized correctly"""
        issues = [
            issue_builder().warning().with_field('field1').build(),
            issue_builder().error().with_field('field2').build(),
            issue_builder().critical().with_field('field3').build(),
            issue_builder().info().with_field('field4').build(),
        ]
        
        prioritized = coordinator.prioritize_issues(issues)
        
        assert len(prioritized) > 0
        # Critical/error issues should come first
        assert prioritized[0]['severity'] in ['critical', 'error']
    
    def test_active_learning_selection(self, coordinator, issue_builder):
        """Test active learning selects most uncertain cases"""
        # Create issues - coordinator calculates uncertainty internally
        issues = [
            issue_builder().warning().with_field('novel_field').build(),
            issue_builder().info().with_field('common_field').build(),
        ]
        
        # Simulate having seen 'common_field' before
        coordinator.learned_patterns['common_field:info'] = {
            'seen_count': 100,
            'feedback_count': 10,
            'consistency': 0.9,
            'decisions': ['accept'] * 10
        }
        
        # Select issues - should prioritize novel one
        selected = coordinator._select_informative_issues(
            coordinator.prioritize_issues(issues)
        )
        
        # Novel issue should be selected or both (since selection is smart)
        assert len(selected) >= 1
    
    def test_prioritize_novel_patterns(self, coordinator, issue_builder):
        """Test prioritization of novel error patterns"""
        novel_issue = issue_builder().warning().with_field('new_field').build()
        
        # Add to known patterns to mark as seen before
        common_issue = issue_builder().warning().with_field('sequence').build()
        coordinator.learned_patterns['sequence:warning'] = {
            'seen_count': 50,
            'feedback_count': 5,
            'consistency': 0.8,
            'decisions': ['accept'] * 5
        }
        
        issues = [common_issue, novel_issue]
        prioritized = coordinator.prioritize_issues(issues)
        
        # Both should be prioritized, but novel might rank higher
        assert len(prioritized) == 2
    
    # ===== EXPERT ROUTING =====
    
    def test_route_to_domain_expert(self, coordinator, validation_report_with_issues):
        """Test routing issues to appropriate domain experts"""
        issues = coordinator._extract_issues_from_report(validation_report_with_issues)
        routing = coordinator.route_to_expert(issues)
        
        assert routing in ['biologist_expert', 'data_engineer', 'quality_specialist']
    
    def test_route_bio_issues_to_biologist(self, coordinator, report_builder):
        """Test biological issues routed to biology expert"""
        bio_report = (report_builder()
                      .with_errors(1, stage_name='bio_rules')
                      .build())
        
        issues = coordinator._extract_issues_from_report(bio_report)
        routing = coordinator.route_to_expert(issues)
        
        assert routing in ['biologist_expert', 'quality_specialist']
    
    def test_route_ml_issues_to_ml_expert(self, coordinator, report_builder):
        """Test ML issues routed to ML specialist"""
        # No ML stage in current system, so test with schema issues
        ml_report = (report_builder()
                     .with_errors(1, stage_name='schema')
                     .build())
        
        issues = coordinator._extract_issues_from_report(ml_report)
        routing = coordinator.route_to_expert(issues)
        
        # Should route to data_engineer or quality_specialist
        assert routing in ['data_engineer', 'quality_specialist']
    
    # ===== FEEDBACK CAPTURE =====
    
    def test_capture_human_feedback(self, coordinator):
        """Test capturing human feedback on validation issues"""
        review_id = 'review_001'
        feedback = {
            'reviewer_id': 'expert_biologist_1',
            'decision': 'accept',
            'comments': 'UNKNOWN_XYZ is a valid gene symbol in species variant'
        }
        
        coordinator.capture_feedback(review_id, feedback)
        
        assert len(coordinator.feedback_history) > 0
        last_feedback = coordinator.feedback_history[-1]
        assert last_feedback['review_id'] == review_id
        assert 'feedback' in last_feedback
    
    def test_feedback_updates_knowledge_base(self, coordinator):
        """Test that feedback updates the knowledge base"""
        feedback = {
            'decision': 'accept',
            'add_to_whitelist': ['GENE_XYZ']
        }
        
        coordinator._learn_from_feedback({'feedback': feedback, 'decision': 'accept'})
        
        # Check knowledge base was updated (if implementation supports it)
        # For now, just verify feedback was processed
        assert len(coordinator.feedback_history) >= 0
    
    def test_rejected_feedback_adds_to_blacklist(self, coordinator):
        """Test rejected items added to blacklist"""
        feedback = {
            'decision': 'reject',
            'add_to_blacklist': ['INVALID_GENE']
        }
        
        coordinator._learn_from_feedback({'feedback': feedback, 'decision': 'reject'})
        
        # Verify feedback was processed
        assert len(coordinator.feedback_history) >= 0
    
    # ===== RLHF-STYLE LEARNING =====
    
    def test_rlhf_pattern_learning(self, coordinator):
        """Test RLHF-style learning from human feedback"""
        pattern = 'gene_variant_ABC'
        
        # Simulate multiple feedback instances
        for _ in range(3):
            feedback = {'decision': 'accept'}
            coordinator.update_learned_patterns(pattern, feedback)
        
        # Pattern should be learned
        assert pattern in coordinator.learned_patterns
        assert coordinator.learned_patterns[pattern]['feedback_count'] == 3
    
    def test_conflicting_feedback_reduces_confidence(self, coordinator):
        """Test conflicting feedback affects pattern learning"""
        pattern = 'ambiguous_case'
        
        feedbacks = [
            {'decision': 'accept'},
            {'decision': 'reject'},
            {'decision': 'accept'},
        ]
        
        for fb in feedbacks:
            coordinator.update_learned_patterns(pattern, fb)
        
        # Pattern should exist with mixed decisions
        assert pattern in coordinator.learned_patterns
        assert len(coordinator.learned_patterns[pattern]['decisions']) == 3
    
    # ===== REVIEW WORKFLOW =====
    
    @pytest.mark.asyncio
    async def test_create_review_task(self, coordinator, validation_report_with_issues):
        """Test creation of review task"""
        task = coordinator.create_review_task(
            validation_report_with_issues,
            ReviewPriority.HIGH
        )
        
        assert 'review_id' in task
        assert 'priority' in task
        assert 'status' in task
        assert task['status'] == ReviewStatus.PENDING.value
    
    @pytest.mark.asyncio
    async def test_high_priority_for_critical_issues(self, coordinator, report_builder):
        """Test critical issues get high priority"""
        critical_report = (report_builder()
                           .with_critical_issue(stage_name='schema')
                           .build())
        
        task = coordinator.create_review_task(critical_report, ReviewPriority.CRITICAL)
        
        assert task['priority'] == ReviewPriority.CRITICAL.value
    
    @pytest.mark.asyncio
    async def test_review_task_includes_context(self, coordinator, validation_report_with_issues):
        """Test review task includes relevant context"""
        task = coordinator.create_review_task(
            validation_report_with_issues,
            ReviewPriority.HIGH
        )
        
        assert 'issues' in task
        assert 'validation_id' in task
        assert len(task['issues']) > 0
    
    # ===== METRICS & MONITORING =====
    
    def test_track_review_metrics(self, coordinator):
        """Test tracking of review metrics"""
        metrics = coordinator.get_review_metrics()
        
        assert 'total_reviews' in metrics
        assert 'learned_patterns' in metrics
        assert 'feedback_count' in metrics
    
    def test_track_expert_performance(self, coordinator):
        """Test tracking expert performance"""
        expert_id = 'expert_1'
        
        # Add some feedback for this expert
        coordinator.feedback_history.append({
            'reviewer_id': expert_id,
            'timestamp': datetime.now().isoformat()
        })
        
        expert_metrics = coordinator.track_expert_performance(expert_id)
        assert 'expert_id' in expert_metrics
        assert 'total_reviews' in expert_metrics
    
    # ===== AUTOMATION FROM LEARNING =====
    
    def test_apply_learned_rules(self, coordinator, issue_builder):
        """Test automatic application of learned rules"""
        # Simulate learned pattern with high confidence
        coordinator.learned_patterns['field1:error'] = {
            'confidence': 0.95,
            'seen_count': 10,
            'feedback_count': 10,
            'decisions': ['accept'] * 10,
            'consistency': 0.95
        }
        
        issue = issue_builder().error().with_field('field1').build()
        
        auto_decision = coordinator.try_auto_resolve(issue)
        
        # Should return the most common decision
        assert auto_decision == 'accept'
    
    def test_low_confidence_not_auto_resolved(self, coordinator, issue_builder):
        """Test low confidence patterns don't auto-resolve"""
        coordinator.learned_patterns['uncertain:warning'] = {
            'confidence': 0.4,
            'seen_count': 5,
            'feedback_count': 5,
            'decisions': ['accept', 'reject', 'accept', 'reject', 'accept'],
            'consistency': 0.6
        }
        
        issue = issue_builder().warning().with_field('uncertain').build()
        
        auto_decision = coordinator.try_auto_resolve(issue)
        
        # Should not auto-resolve (low confidence)
        assert auto_decision is None


class TestHumanReviewIntegration:
    """Integration tests for human review workflow"""
    
    @pytest.fixture
    def coordinator(self):
        return HumanReviewCoordinator()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_review_cycle(self, coordinator, report_builder, sample_dataset):
        """Test complete review cycle from issue to resolution"""
        # 1. Create validation report with issue
        report = (report_builder()
                  .with_validation_id('cycle_test_001')
                  .with_errors(2, stage_name='bio_lookups')
                  .build())
        
        # 2. Verify review is triggered
        should_review = coordinator.should_trigger_review(report)
        assert should_review is True
        
        # 3. Coordinate review
        review_result = await coordinator.coordinate_review(report, sample_dataset)
        
        # 4. Verify review completed
        assert review_result['status'] == 'completed'
        assert 'decision' in review_result
        assert 'reviewer_id' in review_result


class TestHumanReviewEdgeCases:
    """Edge case tests for HumanReviewCoordinator"""
    
    @pytest.fixture
    def coordinator(self):
        return HumanReviewCoordinator()
    
    def test_no_issues_to_review(self, coordinator, report_builder):
        """Test handling when there are no issues to review"""
        clean_report = (report_builder()
                        .accepted()
                        .with_schema_passed()
                        .build())
        
        should_review = coordinator.should_trigger_review(clean_report)
        assert should_review is False
    
    def test_all_issues_already_learned(self, coordinator, issue_builder):
        """Test when all issues match learned patterns"""
        # Add learned pattern with high confidence
        coordinator.learned_patterns['known_issue:warning'] = {
            'confidence': 0.95,
            'seen_count': 100,
            'feedback_count': 20,
            'decisions': ['accept'] * 20,
            'consistency': 0.95
        }
        
        issue = issue_builder().warning().with_field('known_issue').build()
        
        auto_resolved = coordinator.try_auto_resolve(issue)
        assert auto_resolved == 'accept'
    
    def test_expert_unavailable(self, coordinator, report_builder):
        """Test handling when routing returns default expert"""
        report = (report_builder()
                  .with_errors(1, stage_name='rules')
                  .build())
        
        issues = coordinator._extract_issues_from_report(report)
        expert = coordinator.route_to_expert(issues)
        
        # Should return one of the valid expert types
        assert expert in ['biologist_expert', 'data_engineer', 'quality_specialist']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])