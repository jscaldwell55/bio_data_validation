"""
Unit tests for Human Review Coordinator
Tests HITL mechanisms, active learning, and feedback loops
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from src.agents.human_review_coordinator import HumanReviewCoordinator
from src.schemas.base_schemas import (
    ValidationReport,
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
    def validation_report_with_issues(self):
        """Validation report with various issues"""
        return {
            'validation_id': 'test_val_001',
            'dataset_id': 'dataset_001',
            'final_decision': 'CONDITIONAL_ACCEPT',
            'requires_human_review': True,
            'stages': {
                'bio_lookups': {
                    'issues': [
                        ValidationIssue(
                            field='target_gene',
                            message='Gene UNKNOWN_XYZ not found in NCBI',
                            severity=ValidationSeverity.ERROR,
                            record_id='gRNA_001'
                        ),
                        ValidationIssue(
                            field='target_gene',
                            message='Ambiguous gene symbol: ABC1',
                            severity=ValidationSeverity.WARNING,
                            record_id='gRNA_002'
                        )
                    ]
                }
            }
        }
    
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
    
    @pytest.mark.asyncio
    async def test_review_triggered_for_critical_issues(self, coordinator, validation_report_with_issues):
        """Test that critical issues trigger review"""
        # Add critical issue
        validation_report_with_issues['stages']['schema'] = {
            'issues': [
                ValidationIssue(
                    field='dataset',
                    message='Critical data corruption detected',
                    severity=ValidationSeverity.CRITICAL
                )
            ]
        }
        
        should_review = coordinator.should_trigger_review(validation_report_with_issues)
        
        assert should_review is True
    
    @pytest.mark.asyncio
    async def test_review_not_triggered_for_clean_data(self, coordinator):
        """Test that clean data doesn't trigger review"""
        clean_report = {
            'validation_id': 'test_val_002',
            'final_decision': 'ACCEPTED',
            'requires_human_review': False,
            'stages': {}
        }
        
        should_review = coordinator.should_trigger_review(clean_report)
        
        assert should_review is False
    
    @pytest.mark.asyncio
    async def test_review_triggered_by_error_threshold(self, coordinator):
        """Test review triggered when error count exceeds threshold"""
        report_with_many_errors = {
            'validation_id': 'test_val_003',
            'final_decision': 'CONDITIONAL_ACCEPT',
            'requires_human_review': True,
            'stages': {
                'rules': {
                    'issues': [
                        ValidationIssue(
                            field=f'field_{i}',
                            message=f'Error {i}',
                            severity=ValidationSeverity.ERROR
                        )
                        for i in range(5)  # 5 errors
                    ]
                }
            }
        }
        
        coordinator.config.error_threshold = 3
        should_review = coordinator.should_trigger_review(report_with_many_errors)
        
        assert should_review is True
    
    # ===== ACTIVE LEARNING / PRIORITIZATION =====
    
    @pytest.mark.asyncio
    async def test_issue_prioritization(self, coordinator, validation_report_with_issues):
        """Test that issues are prioritized correctly"""
        prioritized = coordinator.prioritize_issues(validation_report_with_issues)
        
        assert len(prioritized) > 0
        
        # Critical and error issues should come first
        first_issue = prioritized[0]
        assert first_issue.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]
    
    @pytest.mark.asyncio
    async def test_active_learning_selection(self, coordinator, validation_report_with_issues):
        """Test active learning selects most uncertain cases"""
        # Add uncertainty scores
        issues_with_uncertainty = []
        for issue in validation_report_with_issues['stages']['bio_lookups']['issues']:
            issue.uncertainty_score = 0.8  # High uncertainty
            issues_with_uncertainty.append(issue)
        
        selected = coordinator.select_for_active_learning(issues_with_uncertainty, max_count=1)
        
        assert len(selected) == 1
        assert selected[0].uncertainty_score >= 0.7  # Selected high uncertainty
    
    @pytest.mark.asyncio
    async def test_prioritize_novel_patterns(self, coordinator):
        """Test prioritization of novel error patterns"""
        novel_issue = ValidationIssue(
            field='new_field',
            message='Never seen this error before',
            severity=ValidationSeverity.WARNING,
            is_novel=True
        )
        
        common_issue = ValidationIssue(
            field='sequence',
            message='Invalid PAM',
            severity=ValidationSeverity.WARNING,
            is_novel=False
        )
        
        issues = [common_issue, novel_issue]
        prioritized = coordinator.prioritize_issues(issues)

        # Novel issue should be prioritized
        assert prioritized[0]['is_novel'] is True
    
    # ===== EXPERT ROUTING =====
    
    @pytest.mark.asyncio
    async def test_route_to_domain_expert(self, coordinator, validation_report_with_issues):
        """Test routing issues to appropriate domain experts"""
        routing = coordinator.route_to_expert(validation_report_with_issues)
        
        assert 'expert_type' in routing
        assert routing['expert_type'] in ['bioinformatics', 'biology', 'data_quality', 'ml_specialist']
    
    @pytest.mark.asyncio
    async def test_route_bio_issues_to_biologist(self, coordinator):
        """Test biological issues routed to biology expert"""
        bio_report = {
            'validation_id': 'test_val_004',
            'stages': {
                'bio_rules': {
                    'issues': [
                        ValidationIssue(
                            field='pam_sequence',
                            message='Invalid PAM for SpCas9',
                            severity=ValidationSeverity.ERROR
                        )
                    ]
                }
            }
        }
        
        routing = coordinator.route_to_expert(bio_report)
        
        assert routing['expert_type'] in ['bioinformatics', 'biology']
    
    @pytest.mark.asyncio
    async def test_route_ml_issues_to_ml_expert(self, coordinator):
        """Test ML issues routed to ML specialist"""
        ml_report = {
            'validation_id': 'test_val_005',
            'stages': {
                'ml_integrity': {
                    'issues': [
                        ValidationIssue(
                            field='dataset',
                            message='Data leakage detected',
                            severity=ValidationSeverity.CRITICAL
                        )
                    ]
                }
            }
        }
        
        routing = coordinator.route_to_expert(ml_report)
        
        assert routing['expert_type'] == 'ml_specialist'
    
    # ===== FEEDBACK CAPTURE =====
    
    @pytest.mark.asyncio
    async def test_capture_human_feedback(self, coordinator, validation_report_with_issues):
        """Test capturing human feedback on validation issues"""
        feedback = {
            'validation_id': 'test_val_001',
            'reviewer': 'expert_biologist_1',
            'issue_id': 'issue_001',
            'decision': 'accept',
            'reasoning': 'UNKNOWN_XYZ is a valid gene symbol in species variant',
            'timestamp': datetime.now()
        }
        
        result = coordinator.capture_feedback(validation_report_with_issues, feedback)
        
        assert result['status'] == 'feedback_captured'
        assert 'feedback_id' in result
    
    @pytest.mark.asyncio
    async def test_feedback_updates_knowledge_base(self, coordinator):
        """Test that feedback updates the knowledge base"""
        feedback = {
            'validation_id': 'test_val_001',
            'issue_id': 'issue_001',
            'decision': 'accept',
            'new_rule': 'GENE_XYZ is valid for organism variant ABC',
            'add_to_whitelist': ['GENE_XYZ']
        }
        
        coordinator.capture_feedback({}, feedback)
        
        # Check knowledge base was updated
        assert 'GENE_XYZ' in coordinator.knowledge_base.get('whitelisted_genes', [])
    
    @pytest.mark.asyncio
    async def test_rejected_feedback_adds_to_blacklist(self, coordinator):
        """Test rejected items added to blacklist"""
        feedback = {
            'validation_id': 'test_val_001',
            'issue_id': 'issue_001',
            'decision': 'reject',
            'add_to_blacklist': ['INVALID_GENE']
        }
        
        coordinator.capture_feedback({}, feedback)
        
        assert 'INVALID_GENE' in coordinator.knowledge_base.get('blacklisted_genes', [])
    
    # ===== RLHF-STYLE LEARNING =====
    
    @pytest.mark.asyncio
    async def test_rlhf_pattern_learning(self, coordinator):
        """Test RLHF-style learning from human feedback"""
        # Simulate multiple feedback instances
        feedbacks = [
            {'decision': 'accept', 'pattern': 'gene_variant_ABC'},
            {'decision': 'accept', 'pattern': 'gene_variant_ABC'},
            {'decision': 'accept', 'pattern': 'gene_variant_ABC'},
        ]
        
        for fb in feedbacks:
            coordinator.update_learned_patterns(fb)
        
        # Pattern should be learned after multiple confirmations
        assert 'gene_variant_ABC' in coordinator.learned_patterns
        assert coordinator.learned_patterns['gene_variant_ABC']['confidence'] > 0.8
    
    @pytest.mark.asyncio
    async def test_conflicting_feedback_reduces_confidence(self, coordinator):
        """Test conflicting feedback reduces pattern confidence"""
        feedbacks = [
            {'decision': 'accept', 'pattern': 'ambiguous_case'},
            {'decision': 'reject', 'pattern': 'ambiguous_case'},
            {'decision': 'accept', 'pattern': 'ambiguous_case'},
        ]
        
        for fb in feedbacks:
            coordinator.update_learned_patterns(fb)
        
        # Conflicting feedback should result in lower confidence
        if 'ambiguous_case' in coordinator.learned_patterns:
            assert coordinator.learned_patterns['ambiguous_case']['confidence'] < 0.7
    
    # ===== REVIEW WORKFLOW =====
    
    @pytest.mark.asyncio
    async def test_create_review_task(self, coordinator, validation_report_with_issues, sample_dataset):
        """Test creation of review task"""
        task = await coordinator.create_review_task(
            validation_report_with_issues,
            sample_dataset
        )
        
        assert 'task_id' in task
        assert 'priority' in task
        assert 'assigned_expert' in task
        assert 'issues' in task
        assert task['status'] == ReviewStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_high_priority_for_critical_issues(self, coordinator):
        """Test critical issues get high priority"""
        critical_report = {
            'validation_id': 'test_val_006',
            'stages': {
                'schema': {
                    'issues': [
                        ValidationIssue(
                            field='dataset',
                            message='Critical error',
                            severity=ValidationSeverity.CRITICAL
                        )
                    ]
                }
            }
        }
        
        task = await coordinator.create_review_task(critical_report, pd.DataFrame())
        
        assert task['priority'] == ReviewPriority.HIGH
    
    @pytest.mark.asyncio
    async def test_review_task_includes_context(self, coordinator, validation_report_with_issues, sample_dataset):
        """Test review task includes relevant context"""
        task = await coordinator.create_review_task(
            validation_report_with_issues,
            sample_dataset
        )
        
        assert 'context' in task
        assert 'affected_records' in task['context']
        assert 'validation_summary' in task['context']
    
    # ===== METRICS & MONITORING =====
    
    @pytest.mark.asyncio
    async def test_track_review_metrics(self, coordinator):
        """Test tracking of review metrics"""
        metrics = coordinator.get_review_metrics()
        
        assert 'total_reviews' in metrics
        assert 'average_review_time' in metrics
        assert 'agreement_rate' in metrics
    
    @pytest.mark.asyncio
    async def test_track_expert_performance(self, coordinator):
        """Test tracking expert performance"""
        feedback = {
            'reviewer': 'expert_1',
            'decision': 'accept',
            'review_time_seconds': 120
        }
        
        coordinator.track_expert_performance(feedback)
        
        expert_metrics = coordinator.get_expert_metrics('expert_1')
        assert expert_metrics['review_count'] >= 1
    
    # ===== AUTOMATION FROM LEARNING =====
    
    @pytest.mark.asyncio
    async def test_apply_learned_rules(self, coordinator):
        """Test automatic application of learned rules"""
        # Simulate learned pattern
        coordinator.learned_patterns['accept_GENE_ABC'] = {
            'confidence': 0.95,
            'rule': 'accept GENE_ABC as valid'
        }
        
        issue = ValidationIssue(
            field='target_gene',
            message='Gene GENE_ABC not found',
            severity=ValidationSeverity.ERROR,
            value='GENE_ABC'
        )
        
        auto_decision = coordinator.try_auto_resolve(issue)
        
        assert auto_decision is not None
        assert auto_decision['action'] == 'accept'
        assert auto_decision['confidence'] >= 0.9
    
    @pytest.mark.asyncio
    async def test_low_confidence_not_auto_resolved(self, coordinator):
        """Test low confidence patterns don't auto-resolve"""
        coordinator.learned_patterns['uncertain_pattern'] = {
            'confidence': 0.4,
            'rule': 'uncertain rule'
        }
        
        issue = ValidationIssue(
            field='test',
            message='Uncertain issue',
            severity=ValidationSeverity.WARNING
        )
        
        auto_decision = coordinator.try_auto_resolve(issue)
        
        assert auto_decision is None or auto_decision['requires_human_review'] is True


class TestHumanReviewIntegration:
    """Integration tests for human review workflow"""
    
    @pytest.fixture
    def coordinator(self):
        return HumanReviewCoordinator()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_review_cycle(self, coordinator):
        """Test complete review cycle from issue to resolution"""
        # 1. Create validation report with issue
        report = {
            'validation_id': 'cycle_test_001',
            'stages': {
                'bio_lookups': {
                    'issues': [
                        ValidationIssue(
                            field='target_gene',
                            message='Unknown gene NEWGENE1',
                            severity=ValidationSeverity.ERROR
                        )
                    ]
                }
            }
        }
        
        # 2. Create review task
        task = await coordinator.create_review_task(report, pd.DataFrame())
        assert task['status'] == ReviewStatus.PENDING
        
        # 3. Assign to expert
        coordinator.assign_task(task['task_id'], 'expert_1')
        
        # 4. Submit feedback
        feedback = {
            'task_id': task['task_id'],
            'decision': 'accept',
            'reasoning': 'NEWGENE1 is valid novel gene',
            'add_to_whitelist': ['NEWGENE1']
        }
        coordinator.capture_feedback(report, feedback)
        
        # 5. Verify knowledge updated
        assert 'NEWGENE1' in coordinator.knowledge_base.get('whitelisted_genes', [])
        
        # 6. Verify task completed
        updated_task = coordinator.get_task(task['task_id'])
        assert updated_task['status'] == ReviewStatus.COMPLETED


class TestHumanReviewEdgeCases:
    """Edge case tests for HumanReviewCoordinator"""
    
    @pytest.fixture
    def coordinator(self):
        return HumanReviewCoordinator()
    
    @pytest.mark.asyncio
    async def test_no_issues_to_review(self, coordinator):
        """Test handling when there are no issues to review"""
        clean_report = {
            'validation_id': 'clean_001',
            'final_decision': 'ACCEPTED',
            'stages': {}
        }
        
        should_review = coordinator.should_trigger_review(clean_report)
        assert should_review is False
    
    @pytest.mark.asyncio
    async def test_all_issues_already_learned(self, coordinator):
        """Test when all issues match learned patterns"""
        # Add learned pattern
        coordinator.learned_patterns['known_issue'] = {
            'confidence': 0.95,
            'action': 'accept'
        }
        
        report = {
            'validation_id': 'learned_001',
            'stages': {
                'test': {
                    'issues': [
                        ValidationIssue(
                            field='test',
                            message='known_issue',
                            severity=ValidationSeverity.WARNING,
                            pattern_id='known_issue'
                        )
                    ]
                }
            }
        }
        
        auto_resolved = coordinator.auto_resolve_issues(report)
        assert len(auto_resolved) > 0
    
    @pytest.mark.asyncio
    async def test_expert_unavailable(self, coordinator):
        """Test handling when no expert is available"""
        report = {'validation_id': 'test_001', 'stages': {}}
        
        with patch.object(coordinator, 'find_available_expert', return_value=None):
            task = await coordinator.create_review_task(report, pd.DataFrame())
            
            assert task['assigned_expert'] in [None, 'unassigned']
            assert task['status'] == ReviewStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])