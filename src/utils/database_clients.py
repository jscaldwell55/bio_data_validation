# src/utils/database_clients.py
"""
Database client utilities for validation data storage.
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

Base = declarative_base()


class ValidationRun(Base):
    """Validation run record"""
    __tablename__ = "validation_runs"

    # Primary columns
    id = Column(String, primary_key=True)
    dataset_id = Column(String, index=True)
    format_type = Column(String)
    record_count = Column(Integer, nullable=True)
    
    # Timestamp columns
    submitted_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Status and decision columns
    status = Column(String)
    final_decision = Column(String, nullable=True)
    execution_time_seconds = Column(Float, nullable=True)
    requires_human_review = Column(Boolean, default=False)
    short_circuited = Column(Boolean, default=False)
    
    # Data columns
    report_json = Column(JSON)
    dataset_metadata = Column(JSON)  # FIXED: Cannot use 'metadata' (SQLAlchemy reserved word)

    def __init__(self, validation_id=None, start_time=None, metadata=None, **kwargs):
        """
        Flexible constructor supporting multiple naming conventions.

        Args:
            validation_id: Maps to 'id'
            start_time: Maps to 'submitted_at'
            metadata: Maps to 'dataset_metadata' (avoiding SQLAlchemy reserved word)
            **kwargs: Other column values (dataset_id, format_type, etc.)
        """
        # Map validation_id to id
        if validation_id is not None:
            kwargs['id'] = validation_id

        # Map start_time to submitted_at
        if start_time is not None:
            kwargs['submitted_at'] = start_time
        
        # Map metadata to dataset_metadata (SQLAlchemy reserves 'metadata')
        if metadata is not None:
            kwargs['dataset_metadata'] = metadata

        super().__init__(**kwargs)


# CRITICAL: Add properties AFTER class definition to avoid SQLAlchemy confusion
# Properties defined inside the class body are treated as columns by SQLAlchemy
ValidationRun.validation_id = property(lambda self: self.id)
ValidationRun.metadata = property(lambda self: self.dataset_metadata)


class ValidationIssue(Base):
    """Individual validation issue"""
    __tablename__ = "validation_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    validation_run_id = Column(String, index=True)
    stage = Column(String)
    validator_name = Column(String)
    field = Column(String)
    message = Column(Text)
    severity = Column(String, index=True)
    rule_id = Column(String, nullable=True)
    issue_metadata = Column(JSON)  # FIXED: Cannot use 'metadata' (SQLAlchemy reserved word)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, validation_id=None, record_id=None, metadata=None, **kwargs):
        """
        Flexible constructor supporting multiple naming conventions.

        Args:
            validation_id: Maps to 'validation_run_id'
            record_id: Also maps to 'validation_run_id'
            metadata: Maps to 'issue_metadata'
            **kwargs: Other column values
        """
        # Map validation_id or record_id to validation_run_id
        if validation_id is not None:
            kwargs['validation_run_id'] = validation_id
        elif record_id is not None:
            kwargs['validation_run_id'] = record_id
        
        # Map metadata to issue_metadata (SQLAlchemy reserves 'metadata')
        if metadata is not None:
            kwargs['issue_metadata'] = metadata

        super().__init__(**kwargs)


# Add property after class definition
ValidationIssue.metadata = property(lambda self: self.issue_metadata)


class HumanReview(Base):
    """Human review record"""
    __tablename__ = "human_reviews"

    id = Column(String, primary_key=True)
    validation_run_id = Column(String, index=True)
    reviewer_id = Column(String)
    status = Column(String)
    priority = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    decision = Column(String, nullable=True)
    feedback = Column(JSON)
    review_metadata = Column(JSON)  # FIXED: Cannot use 'metadata' (SQLAlchemy reserved word)

    def __init__(self, validation_id=None, reviewer=None, metadata=None, **kwargs):
        """
        Flexible constructor supporting multiple naming conventions.

        Args:
            validation_id: Maps to 'validation_run_id'
            reviewer: Maps to 'reviewer_id'
            metadata: Maps to 'review_metadata'
            **kwargs: Other column values
        """
        # Map validation_id to validation_run_id
        if validation_id is not None:
            kwargs['validation_run_id'] = validation_id

        # Map reviewer to reviewer_id
        if reviewer is not None:
            kwargs['reviewer_id'] = reviewer
        
        # Map metadata to review_metadata (SQLAlchemy reserves 'metadata')
        if metadata is not None:
            kwargs['review_metadata'] = metadata

        super().__init__(**kwargs)


# Add property after class definition
HumanReview.metadata = property(lambda self: self.review_metadata)


class DatabaseClient:
    """Database client for validation system"""
    
    def __init__(self, database_url: str):
        """
        Initialize database client.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def save_validation_run(
        self,
        validation_id: str,
        dataset_id: str,
        format_type: str,
        record_count: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> ValidationRun:
        """Save validation run to database"""
        session = self.get_session()
        
        try:
            run = ValidationRun(
                id=validation_id,
                dataset_id=dataset_id,
                format_type=format_type,
                record_count=record_count,
                status="pending",
                dataset_metadata=metadata or {}
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run
            
        finally:
            session.close()
    
    def update_validation_run(
        self,
        validation_id: str,
        report: Dict[str, Any]
    ):
        """Update validation run with results"""
        session = self.get_session()
        
        try:
            run = session.query(ValidationRun).filter_by(id=validation_id).first()
            if run:
                run.completed_at = datetime.utcnow()
                run.status = "completed"
                run.final_decision = report.get("final_decision")
                run.execution_time_seconds = report.get("execution_time_seconds")
                run.requires_human_review = report.get("requires_human_review", False)
                run.short_circuited = report.get("short_circuited", False)
                run.report_json = report
                session.commit()
                
        finally:
            session.close()
    
    def save_validation_issues(
        self,
        validation_id: str,
        report: Dict[str, Any]
    ):
        """Save validation issues to database"""
        session = self.get_session()
        
        try:
            for stage_name, stage_data in report.get("stages", {}).items():
                for issue in stage_data.get("issues", []):
                    db_issue = ValidationIssue(
                        validation_run_id=validation_id,
                        stage=stage_name,
                        validator_name=stage_data.get("validator_name"),
                        field=issue.get("field"),
                        message=issue.get("message"),
                        severity=issue.get("severity"),
                        rule_id=issue.get("rule_id"),
                        issue_metadata=issue.get("metadata", {})
                    )
                    session.add(db_issue)
            
            session.commit()
            
        finally:
            session.close()
    
    def get_validation_run(self, validation_id: str) -> Optional[ValidationRun]:
        """Get validation run by ID"""
        session = self.get_session()
        
        try:
            return session.query(ValidationRun).filter_by(id=validation_id).first()
        finally:
            session.close()
    
    def get_validation_issues(
        self,
        validation_id: str,
        severity: Optional[str] = None
    ) -> List[ValidationIssue]:
        """Get validation issues for a run"""
        session = self.get_session()
        
        try:
            query = session.query(ValidationIssue).filter_by(
                validation_run_id=validation_id
            )
            
            if severity:
                query = query.filter_by(severity=severity)
            
            return query.all()
            
        finally:
            session.close()
    
    def get_recent_validations(
        self,
        limit: int = 10,
        dataset_id: Optional[str] = None
    ) -> List[ValidationRun]:
        """Get recent validation runs"""
        session = self.get_session()
        
        try:
            query = session.query(ValidationRun).order_by(
                ValidationRun.submitted_at.desc()
            )
            
            if dataset_id:
                query = query.filter_by(dataset_id=dataset_id)
            
            return query.limit(limit).all()
            
        finally:
            session.close()
    
    def create_human_review(
        self,
        validation_id: str,
        priority: str,
        metadata: Optional[Dict] = None
    ) -> HumanReview:
        """Create human review record"""
        session = self.get_session()
        
        try:
            review = HumanReview(
                id=f"review_{validation_id}",
                validation_run_id=validation_id,
                reviewer_id="pending",
                status="pending",
                priority=priority,
                review_metadata=metadata or {}
            )
            session.add(review)
            session.commit()
            session.refresh(review)
            return review
            
        finally:
            session.close()
    
    def update_human_review(
        self,
        review_id: str,
        reviewer_id: str,
        decision: str,
        feedback: Dict[str, Any]
    ):
        """Update human review with decision"""
        session = self.get_session()
        
        try:
            review = session.query(HumanReview).filter_by(id=review_id).first()
            if review:
                review.reviewer_id = reviewer_id
                review.reviewed_at = datetime.utcnow()
                review.status = "completed"
                review.decision = decision
                review.feedback = feedback
                session.commit()
                
        finally:
            session.close()
    
    def get_pending_reviews(self) -> List[HumanReview]:
        """Get all pending human reviews"""
        session = self.get_session()
        
        try:
            return session.query(HumanReview).filter_by(
                status="pending"
            ).order_by(HumanReview.priority.desc()).all()
            
        finally:
            session.close()