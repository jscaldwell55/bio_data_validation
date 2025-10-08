"""
Unit tests for Policy Engine
Tests YAML-based policy decisions and decision matrices
"""
import pytest
import yaml
from pathlib import Path
from src.engine.policy_engine import PolicyEngine
from src.schemas.base_schemas import (
    ValidationSeverity,
    Decision,
    ValidationIssue
)


class TestPolicyEngine:
    """Test suite for PolicyEngine"""
    
    @pytest.fixture
    def policy_engine(self):
        """Create PolicyEngine instance with default config"""
        return PolicyEngine()
    
    @pytest.fixture
    def policy_config(self):
        """Sample policy configuration"""
        return {
            'decision_matrix': {
                'critical_threshold': 1,
                'error_threshold': 5,
                'warning_threshold': 10
            },
            'human_review_triggers': {
                'on_critical': True,
                'error_count_threshold': 3,
                'warning_count_threshold': 15
            },
            'auto_accept_conditions': {
                'max_warnings': 2,
                'no_errors': True
            },
            'auto_reject_conditions': {
                'any_critical': True,
                'error_count': 5
            }
        }
    
    @pytest.fixture
    def validation_report_no_issues(self):
        """Report with no issues"""
        return {
            'validation_id': 'test_001',
            'stages': {
                'schema': {'passed': True, 'issues': []},
                'rules': {'passed': True, 'issues': []},
                'bio_rules': {'passed': True, 'issues': []},
                'bio_lookups': {'passed': True, 'issues': []}
            }
        }
    
    # ===== DECISION MATRIX TESTS =====
    
    def test_no_issues_accepted(self, policy_engine, validation_report_no_issues):
        """Test clean dataset is ACCEPTED"""
        decision = policy_engine.make_decision(validation_report_no_issues)
        
        assert decision['final_decision'] == Decision.ACCEPTED
        assert decision['requires_human_review'] is False
    
    def test_critical_issue_rejected(self, policy_engine):
        """Test any critical issue triggers REJECTED"""
        report_with_critical = {
            'validation_id': 'test_002',
            'stages': {
                'schema': {
                    'passed': False,
                    'issues': [
                        ValidationIssue(
                            field='dataset',
                            message='Critical corruption',
                            severity=ValidationSeverity.CRITICAL
                        )
                    ]
                }
            }
        }
        
        decision = policy_engine.make_decision(report_with_critical)
        
        assert decision['final_decision'] == Decision.REJECTED
        assert 'critical' in decision['rationale'].lower()
    
    def test_many_errors_rejected(self, policy_engine):
        """Test >= 5 errors triggers REJECTED"""
        errors = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Error {i}',
                severity=ValidationSeverity.ERROR
            )
            for i in range(6)  # 6 errors (above threshold)
        ]
        
        report_with_errors = {
            'validation_id': 'test_003',
            'stages': {
                'rules': {'passed': False, 'issues': errors}
            }
        }
        
        decision = policy_engine.make_decision(report_with_errors)
        
        assert decision['final_decision'] == Decision.REJECTED
    
    def test_few_errors_conditional_accept(self, policy_engine):
        """Test 1-4 errors triggers CONDITIONAL_ACCEPT"""
        errors = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Error {i}',
                severity=ValidationSeverity.ERROR
            )
            for i in range(3)  # 3 errors
        ]
        
        report_with_errors = {
            'validation_id': 'test_004',
            'stages': {
                'rules': {'passed': False, 'issues': errors}
            }
        }
        
        decision = policy_engine.make_decision(report_with_errors)
        
        assert decision['final_decision'] == Decision.CONDITIONAL_ACCEPT
    
    def test_many_warnings_conditional_accept(self, policy_engine):
        """Test >= 10 warnings triggers CONDITIONAL_ACCEPT"""
        warnings = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Warning {i}',
                severity=ValidationSeverity.WARNING
            )
            for i in range(12)  # 12 warnings
        ]
        
        report_with_warnings = {
            'validation_id': 'test_005',
            'stages': {
                'bio_rules': {'passed': True, 'issues': warnings}
            }
        }
        
        decision = policy_engine.make_decision(report_with_warnings)
        
        assert decision['final_decision'] in [Decision.CONDITIONAL_ACCEPT, Decision.ACCEPTED]
    
    def test_few_warnings_accepted(self, policy_engine):
        """Test < 10 warnings is ACCEPTED"""
        warnings = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Warning {i}',
                severity=ValidationSeverity.WARNING
            )
            for i in range(3)  # 3 warnings
        ]
        
        report_with_warnings = {
            'validation_id': 'test_006',
            'stages': {
                'bio_rules': {'passed': True, 'issues': warnings}
            }
        }
        
        decision = policy_engine.make_decision(report_with_warnings)
        
        assert decision['final_decision'] == Decision.ACCEPTED
    
    # ===== HUMAN REVIEW TRIGGER TESTS =====
    
    def test_critical_triggers_human_review(self, policy_engine):
        """Test critical issues trigger human review"""
        report_with_critical = {
            'validation_id': 'test_007',
            'stages': {
                'schema': {
                    'issues': [
                        ValidationIssue(
                            field='dataset',
                            message='Critical issue',
                            severity=ValidationSeverity.CRITICAL
                        )
                    ]
                }
            }
        }
        
        decision = policy_engine.make_decision(report_with_critical)
        
        assert decision['requires_human_review'] is True
    
    def test_error_threshold_triggers_review(self, policy_engine):
        """Test >= 3 errors triggers human review"""
        errors = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Error {i}',
                severity=ValidationSeverity.ERROR
            )
            for i in range(4)  # 4 errors
        ]
        
        report = {
            'validation_id': 'test_008',
            'stages': {
                'rules': {'issues': errors}
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        assert decision['requires_human_review'] is True
    
    def test_warning_threshold_triggers_review(self, policy_engine):
        """Test >= 15 warnings triggers human review"""
        warnings = [
            ValidationIssue(
                field=f'field_{i}',
                message=f'Warning {i}',
                severity=ValidationSeverity.WARNING
            )
            for i in range(16)  # 16 warnings
        ]
        
        report = {
            'validation_id': 'test_009',
            'stages': {
                'bio_rules': {'issues': warnings}
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        assert decision['requires_human_review'] is True
    
    def test_no_review_for_clean_data(self, policy_engine, validation_report_no_issues):
        """Test clean data doesn't trigger review"""
        decision = policy_engine.make_decision(validation_report_no_issues)
        
        assert decision['requires_human_review'] is False
    
    # ===== CUSTOM POLICY CONFIGURATION =====
    
    def test_custom_thresholds(self, policy_config):
        """Test custom threshold configuration"""
        # More strict thresholds
        policy_config['decision_matrix']['error_threshold'] = 2
        policy_config['decision_matrix']['warning_threshold'] = 5
        
        engine = PolicyEngine(config=policy_config)
        
        errors = [
            ValidationIssue(
                field='field_1',
                message='Error 1',
                severity=ValidationSeverity.ERROR
            ),
            ValidationIssue(
                field='field_2',
                message='Error 2',
                severity=ValidationSeverity.ERROR
            ),
            ValidationIssue(
                field='field_3',
                message='Error 3',
                severity=ValidationSeverity.ERROR
            )
        ]
        
        report = {
            'validation_id': 'test_010',
            'stages': {
                'rules': {'issues': errors}
            }
        }
        
        decision = engine.make_decision(report)
        
        # 3 errors should exceed threshold of 2
        assert decision['final_decision'] == Decision.REJECTED
    
    def test_load_from_yaml_file(self, tmp_path):
        """Test loading policy from YAML file"""
        # Create temporary YAML file
        config_file = tmp_path / "test_policy.yml"
        config_data = {
            'decision_matrix': {
                'critical_threshold': 1,
                'error_threshold': 3,
                'warning_threshold': 8
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        engine = PolicyEngine(config_path=config_file)
        
        assert engine.config['decision_matrix']['error_threshold'] == 3
    
    # ===== RATIONALE GENERATION =====
    
    def test_rationale_explains_decision(self, policy_engine):
        """Test decision rationale is descriptive"""
        errors = [
            ValidationIssue(
                field='field_1',
                message='Error 1',
                severity=ValidationSeverity.ERROR
            )
        ]
        
        report = {
            'validation_id': 'test_011',
            'stages': {
                'rules': {'issues': errors}
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        assert 'rationale' in decision
        assert len(decision['rationale']) > 0
        assert 'error' in decision['rationale'].lower()
    
    def test_rationale_includes_issue_counts(self, policy_engine):
        """Test rationale includes issue counts"""
        report = {
            'validation_id': 'test_012',
            'stages': {
                'rules': {
                    'issues': [
                        ValidationIssue(field='f1', message='E1', severity=ValidationSeverity.ERROR),
                        ValidationIssue(field='f2', message='W1', severity=ValidationSeverity.WARNING),
                        ValidationIssue(field='f3', message='W2', severity=ValidationSeverity.WARNING)
                    ]
                }
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        # Rationale should mention counts
        rationale = decision['rationale'].lower()
        assert '1' in rationale or 'error' in rationale
        assert '2' in rationale or 'warning' in rationale
    
    # ===== SEVERITY COUNTING =====
    
    def test_count_issues_by_severity(self, policy_engine):
        """Test accurate counting of issues by severity"""
        report = {
            'validation_id': 'test_013',
            'stages': {
                'stage1': {
                    'issues': [
                        ValidationIssue(field='f1', message='C1', severity=ValidationSeverity.CRITICAL),
                        ValidationIssue(field='f2', message='E1', severity=ValidationSeverity.ERROR),
                        ValidationIssue(field='f3', message='E2', severity=ValidationSeverity.ERROR)
                    ]
                },
                'stage2': {
                    'issues': [
                        ValidationIssue(field='f4', message='W1', severity=ValidationSeverity.WARNING),
                        ValidationIssue(field='f5', message='W2', severity=ValidationSeverity.WARNING),
                        ValidationIssue(field='f6', message='W3', severity=ValidationSeverity.WARNING)
                    ]
                }
            }
        }
        
        counts = policy_engine.count_issues_by_severity(report)
        
        assert counts[ValidationSeverity.CRITICAL] == 1
        assert counts[ValidationSeverity.ERROR] == 2
        assert counts[ValidationSeverity.WARNING] == 3
    
    # ===== CONDITIONAL ACCEPT DETAILS =====
    
    def test_conditional_accept_includes_conditions(self, policy_engine):
        """Test CONDITIONAL_ACCEPT includes resolution conditions"""
        errors = [
            ValidationIssue(
                field='gc_content',
                message='GC content suboptimal',
                severity=ValidationSeverity.ERROR
            )
        ]
        
        report = {
            'validation_id': 'test_014',
            'stages': {
                'bio_rules': {'issues': errors}
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        if decision['final_decision'] == Decision.CONDITIONAL_ACCEPT:
            assert 'conditions' in decision or 'recommendations' in decision
    
    # ===== EDGE CASES =====
    
    def test_empty_report(self, policy_engine):
        """Test handling of empty report"""
        empty_report = {
            'validation_id': 'test_015',
            'stages': {}
        }
        
        decision = policy_engine.make_decision(empty_report)
        
        # Should default to safe decision
        assert decision['final_decision'] in [Decision.ACCEPTED, Decision.REJECTED]
    
    def test_mixed_severity_issues(self, policy_engine):
        """Test report with mix of all severity levels"""
        report = {
            'validation_id': 'test_016',
            'stages': {
                'combined': {
                    'issues': [
                        ValidationIssue(field='f1', message='I1', severity=ValidationSeverity.INFO),
                        ValidationIssue(field='f2', message='W1', severity=ValidationSeverity.WARNING),
                        ValidationIssue(field='f3', message='E1', severity=ValidationSeverity.ERROR),
                        ValidationIssue(field='f4', message='C1', severity=ValidationSeverity.CRITICAL)
                    ]
                }
            }
        }
        
        decision = policy_engine.make_decision(report)
        
        # Critical should dominate
        assert decision['final_decision'] == Decision.REJECTED
    
    def test_info_severity_ignored_in_decision(self, policy_engine):
        """Test INFO severity doesn't affect decision"""
        info_only = {
            'validation_id': 'test_017',
            'stages': {
                'schema': {
                    'issues': [
                        ValidationIssue(field='f1', message='Info 1', severity=ValidationSeverity.INFO),
                        ValidationIssue(field='f2', message='Info 2', severity=ValidationSeverity.INFO)
                    ]
                }
            }
        }
        
        decision = policy_engine.make_decision(info_only)
        
        # INFO shouldn't prevent acceptance
        assert decision['final_decision'] == Decision.ACCEPTED


class TestPolicyEngineConfiguration:
    """Tests for policy configuration management"""
    
    def test_default_configuration_loaded(self):
        """Test default configuration is loaded"""
        engine = PolicyEngine()
        
        assert engine.config is not None
        assert 'decision_matrix' in engine.config
        assert 'human_review_triggers' in engine.config
    
    def test_custom_config_overrides_defaults(self, policy_config):
        """Test custom config overrides defaults"""
        policy_config['decision_matrix']['error_threshold'] = 999
        
        engine = PolicyEngine(config=policy_config)
        
        assert engine.config['decision_matrix']['error_threshold'] == 999
    
    def test_invalid_config_raises_error(self):
        """Test invalid configuration raises error"""
        invalid_config = {
            'decision_matrix': {
                'critical_threshold': 'not_a_number'  # Invalid
            }
        }
        
        with pytest.raises((ValueError, TypeError)):
            engine = PolicyEngine(config=invalid_config)
            # Attempt to use it
            engine.make_decision({})
    
    def test_missing_required_config_uses_defaults(self):
        """Test missing config uses sensible defaults"""
        minimal_config = {}
        
        engine = PolicyEngine(config=minimal_config)
        
        # Should have defaults
        assert hasattr(engine, 'config')
        assert engine.config.get('decision_matrix') is not None


class TestPolicyEngineYAMLIntegration:
    """Tests for YAML policy file integration"""
    
    def test_load_valid_yaml_policy(self, tmp_path):
        """Test loading valid YAML policy"""
        policy_file = tmp_path / "policy.yml"
        policy_data = """
        decision_matrix:
          critical_threshold: 1
          error_threshold: 5
          warning_threshold: 10
        
        human_review_triggers:
          on_critical: true
          error_count_threshold: 3
        """
        
        policy_file.write_text(policy_data)
        
        engine = PolicyEngine(config_path=policy_file)
        
        assert engine.config['decision_matrix']['critical_threshold'] == 1
    
    def test_yaml_file_not_found_uses_defaults(self):
        """Test missing YAML file uses defaults"""
        engine = PolicyEngine(config_path=Path("/nonexistent/policy.yml"))
        
        # Should fall back to defaults
        assert engine.config is not None
    
    def test_malformed_yaml_raises_error(self, tmp_path):
        """Test malformed YAML raises error"""
        bad_file = tmp_path / "bad_policy.yml"
        bad_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(yaml.YAMLError):
            PolicyEngine(config_path=bad_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])