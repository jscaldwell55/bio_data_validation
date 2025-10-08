"""
Integration tests for database operations
Tests SQLAlchemy models and database interactions
"""
import pytest
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.utils.database_clients import (
    Base,
    ValidationRun,
    ValidationIssue,
    HumanReview,
    DatabaseClient
)
from src.schemas.base_schemas import ValidationSeverity, Decision


class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    @pytest.fixture
    def db_engine(self):
        """Create in-memory test database"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return engine
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session"""
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def db_client(self):
        """Create database client"""
        return DatabaseClient(database_url="sqlite:///:memory:")
    
    # ===== VALIDATION RUN TESTS =====
    
    @pytest.mark.integration
    def test_create_validation_run(self, db_session):
        """Test creating validation run record"""
        validation_run = ValidationRun(
            validation_id="test_val_001",
            dataset_id="dataset_001",
            start_time=datetime.now(),
            end_time=datetime.now(),
            final_decision=Decision.ACCEPTED,
            requires_human_review=False,
            record_count=100
        )
        
        db_session.add(validation_run)
        db_session.commit()
        
        # Retrieve and verify
        retrieved = db_session.query(ValidationRun).filter_by(
            validation_id="test_val_001"
        ).first()
        
        assert retrieved is not None
        assert retrieved.dataset_id == "dataset_001"
        assert retrieved.final_decision == Decision.ACCEPTED
    
    @pytest.mark.integration
    def test_validation_run_with_issues(self, db_session):
        """Test validation run with associated issues"""
        # Create validation run
        validation_run = ValidationRun(
            validation_id="test_val_002",
            dataset_id="dataset_002",
            start_time=datetime.now(),
            end_time=datetime.now(),
            final_decision=Decision.REJECTED,
            requires_human_review=True,
            record_count=50
        )
        db_session.add(validation_run)
        db_session.flush()
        
        # Add issues
        issue1 = ValidationIssue(
            validation_id="test_val_002",
            stage="schema",
            field="sequence",
            message="Invalid characters in sequence",
            severity=ValidationSeverity.ERROR,
            record_id="gRNA_001"
        )
        issue2 = ValidationIssue(
            validation_id="test_val_002",
            stage="bio_rules",
            field="pam_sequence",
            message="Invalid PAM",
            severity=ValidationSeverity.ERROR,
            record_id="gRNA_002"
        )
        
        db_session.add_all([issue1, issue2])
        db_session.commit()
        
        # Retrieve and verify
        retrieved_run = db_session.query(ValidationRun).filter_by(
            validation_id="test_val_002"
        ).first()
        
        assert len(retrieved_run.issues) == 2
    
    # ===== VALIDATION ISSUE TESTS =====
    
    @pytest.mark.integration
    def test_query_issues_by_severity(self, db_session):
        """Test querying issues by severity"""
        # Create validation run
        validation_run = ValidationRun(
            validation_id="test_val_003",
            dataset_id="dataset_003",
            start_time=datetime.now(),
            end_time=datetime.now(),
            final_decision=Decision.CONDITIONAL_ACCEPT,
            record_count=10
        )
        db_session.add(validation_run)
        db_session.flush()
        
        # Add issues with different severities
        issues = [
            ValidationIssue(
                validation_id="test_val_003",
                stage="rules",
                field="field1",
                message="Critical issue",
                severity=ValidationSeverity.CRITICAL
            ),
            ValidationIssue(
                validation_id="test_val_003",
                stage="rules",
                field="field2",
                message="Error issue",
                severity=ValidationSeverity.ERROR
            ),
            ValidationIssue(
                validation_id="test_val_003",
                stage="rules",
                field="field3",
                message="Warning issue",
                severity=ValidationSeverity.WARNING
            )
        ]
        db_session.add_all(issues)
        db_session.commit()
        
        # Query critical issues
        critical_issues = db_session.query(ValidationIssue).filter_by(
            severity=ValidationSeverity.CRITICAL
        ).all()
        
        assert len(critical_issues) == 1
        assert critical_issues[0].message == "Critical issue"
    
    # ===== HUMAN REVIEW TESTS =====
    
    @pytest.mark.integration
    def test_create_human_review(self, db_session):
        """Test creating human review record"""
        review = HumanReview(
            validation_id="test_val_004",
            reviewer="expert_001",
            review_date=datetime.now(),
            decision="accept",
            reasoning="Valid edge case",
            time_spent_seconds=300
        )
        
        db_session.add(review)
        db_session.commit()
        
        # Retrieve and verify
        retrieved = db_session.query(HumanReview).filter_by(
            validation_id="test_val_004"
        ).first()
        
        assert retrieved is not None
        assert retrieved.reviewer == "expert_001"
        assert retrieved.decision == "accept"
    
    @pytest.mark.integration
    def test_multiple_reviews_per_validation(self, db_session):
        """Test multiple reviews for same validation"""
        reviews = [
            HumanReview(
                validation_id="test_val_005",
                reviewer="expert_001",
                review_date=datetime.now(),
                decision="accept",
                reasoning="Looks good"
            ),
            HumanReview(
                validation_id="test_val_005",
                reviewer="expert_002",
                review_date=datetime.now(),
                decision="accept",
                reasoning="I agree"
            )
        ]
        
        db_session.add_all(reviews)
        db_session.commit()
        
        # Query all reviews
        all_reviews = db_session.query(HumanReview).filter_by(
            validation_id="test_val_005"
        ).all()
        
        assert len(all_reviews) == 2
    
    # ===== DATABASE CLIENT TESTS =====
    
    @pytest.mark.integration
    def test_db_client_save_validation_run(self, db_client):
        """Test database client save validation run"""
        report = {
            'validation_id': 'client_test_001',
            'dataset_id': 'dataset_001',
            'start_time': datetime.now().timestamp(),
            'end_time': datetime.now().timestamp(),
            'execution_time_seconds': 5.5,
            'final_decision': Decision.ACCEPTED,
            'requires_human_review': False,
            'stages': {}
        }
        
        result = db_client.save_validation_run(report)
        
        assert result['success'] is True
        assert 'validation_id' in result
    
    @pytest.mark.integration
    def test_db_client_get_validation_run(self, db_client):
        """Test database client retrieve validation run"""
        # First save a run
        report = {
            'validation_id': 'client_test_002',
            'dataset_id': 'dataset_002',
            'start_time': datetime.now().timestamp(),
            'end_time': datetime.now().timestamp(),
            'execution_time_seconds': 3.2,
            'final_decision': Decision.REJECTED,
            'requires_human_review': True,
            'stages': {}
        }
        db_client.save_validation_run(report)
        
        # Then retrieve it
        retrieved = db_client.get_validation_run('client_test_002')
        
        assert retrieved is not None
        assert retrieved['validation_id'] == 'client_test_002'
        assert retrieved['final_decision'] == Decision.REJECTED
    
    @pytest.mark.integration
    def test_db_client_query_by_dataset(self, db_client):
        """Test querying validations by dataset ID"""
        # Create multiple validations for same dataset
        for i in range(3):
            report = {
                'validation_id': f'query_test_{i:03d}',
                'dataset_id': 'dataset_query_001',
                'start_time': datetime.now().timestamp(),
                'end_time': datetime.now().timestamp(),
                'execution_time_seconds': 2.0,
                'final_decision': Decision.ACCEPTED,
                'stages': {}
            }
            db_client.save_validation_run(report)
        
        # Query all validations for dataset
        results = db_client.get_validations_by_dataset('dataset_query_001')
        
        assert len(results) == 3
    
    @pytest.mark.integration
    def test_db_client_get_recent_validations(self, db_client):
        """Test retrieving recent validations"""
        # Create several validations
        for i in range(5):
            report = {
                'validation_id': f'recent_test_{i:03d}',
                'dataset_id': f'dataset_{i:03d}',
                'start_time': datetime.now().timestamp(),
                'end_time': datetime.now().timestamp(),
                'execution_time_seconds': 1.5,
                'final_decision': Decision.ACCEPTED,
                'stages': {}
            }
            db_client.save_validation_run(report)
        
        # Get recent validations
        recent = db_client.get_recent_validations(limit=3)
        
        assert len(recent) <= 3
    
    # ===== TRANSACTION TESTS =====
    
    @pytest.mark.integration
    def test_transaction_rollback_on_error(self, db_session):
        """Test transaction rollback on error"""
        try:
            validation_run = ValidationRun(
                validation_id="rollback_test_001",
                dataset_id="dataset_001",
                start_time=datetime.now(),
                end_time=datetime.now(),
                final_decision=Decision.ACCEPTED,
                record_count=100
            )
            db_session.add(validation_run)
            
            # Cause an error (duplicate primary key)
            duplicate = ValidationRun(
                validation_id="rollback_test_001",  # Same ID
                dataset_id="dataset_002",
                start_time=datetime.now(),
                end_time=datetime.now(),
                final_decision=Decision.REJECTED,
                record_count=50
            )
            db_session.add(duplicate)
            db_session.commit()
            
        except Exception:
            db_session.rollback()
        
        # Verify nothing was committed
        count = db_session.query(ValidationRun).filter_by(
            validation_id="rollback_test_001"
        ).count()
        
        assert count == 0
    
    # ===== PERFORMANCE TESTS =====
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance"""
        import time
        
        # Create 1000 validation issues
        issues = []
        for i in range(1000):
            issues.append(
                ValidationIssue(
                    validation_id=f"bulk_test_{i // 100:03d}",
                    stage="test",
                    field="field",
                    message=f"Issue {i}",
                    severity=ValidationSeverity.WARNING,
                    record_id=f"record_{i:04d}"
                )
            )
        
        start = time.time()
        db_session.bulk_save_objects(issues)
        db_session.commit()
        duration = time.time() - start
        
        # Should complete quickly
        assert duration < 5.0  # Under 5 seconds
        
        # Verify all inserted
        count = db_session.query(ValidationIssue).count()
        assert count == 1000


class TestDatabaseMigrations:
    """Tests for database migrations"""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires Alembic setup")
    def test_migration_up(self):
        """Test applying migrations"""
        # Test would use Alembic to migrate up
        pass
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires Alembic setup")
    def test_migration_down(self):
        """Test rolling back migrations"""
        # Test would use Alembic to migrate down
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])