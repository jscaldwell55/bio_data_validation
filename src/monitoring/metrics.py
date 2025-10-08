# src/monitoring/metrics.py
"""
Prometheus metrics for monitoring validation system.
"""
from prometheus_client import Counter, Histogram, Gauge, Summary, Info
import time
from functools import wraps
from typing import Callable
import logging

logger = logging.getLogger(__name__)

# Validation metrics
validation_requests_total = Counter(
    'validation_requests_total',
    'Total number of validation requests',
    ['dataset_type', 'decision']
)

validation_duration_seconds = Histogram(
    'validation_duration_seconds',
    'Time spent processing validation',
    ['agent', 'stage'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

validation_errors_total = Counter(
    'validation_errors_total',
    'Total number of validation errors',
    ['agent', 'severity']
)

active_validations = Gauge(
    'active_validations',
    'Number of validations currently in progress'
)

human_reviews_pending = Gauge(
    'human_reviews_pending',
    'Number of validations pending human review'
)

validation_records_processed = Counter(
    'validation_records_processed_total',
    'Total number of records processed',
    ['validator']
)

# API metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# External API metrics
external_api_calls_total = Counter(
    'external_api_calls_total',
    'Total external API calls',
    ['provider', 'endpoint', 'status']
)

external_api_duration_seconds = Histogram(
    'external_api_duration_seconds',
    'External API call duration',
    ['provider', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

external_api_batch_size = Histogram(
    'external_api_batch_size',
    'Size of batched API requests',
    ['provider'],
    buckets=[1, 10, 25, 50, 100, 200, 500]
)

# Data quality metrics
issues_detected_total = Counter(
    'issues_detected_total',
    'Total issues detected by severity',
    ['validator', 'severity', 'rule_id']
)

duplicate_records_total = Counter(
    'duplicate_records_total',
    'Total duplicate records detected',
    ['dataset_type']
)

# System metrics
system_info = Info('bio_validation_system', 'System information')

# Initialize system info
system_info.info({
    'version': '0.1.0',
    'python_version': '3.11',
    'service': 'bio-data-validation'
})


# Decorator for tracking validation metrics
def track_validation_metrics(validator_name: str):
    """
    Decorator to track validation execution metrics.
    
    Usage:
        @track_validation_metrics("SchemaValidator")
        def validate(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Record duration
                duration = time.time() - start_time
                validation_duration_seconds.labels(
                    agent=validator_name,
                    stage="complete"
                ).observe(duration)
                
                # Record errors by severity
                if hasattr(result, 'issues'):
                    for issue in result.issues:
                        validation_errors_total.labels(
                            agent=validator_name,
                            severity=issue.severity
                        ).inc()
                        
                        issues_detected_total.labels(
                            validator=validator_name,
                            severity=issue.severity,
                            rule_id=issue.rule_id or "unknown"
                        ).inc()
                
                # Record records processed
                if hasattr(result, 'records_processed'):
                    validation_records_processed.labels(
                        validator=validator_name
                    ).inc(result.records_processed)
                
                return result
                
            except Exception as e:
                validation_errors_total.labels(
                    agent=validator_name,
                    severity="critical"
                ).inc()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                validation_duration_seconds.labels(
                    agent=validator_name,
                    stage="complete"
                ).observe(duration)
                
                if hasattr(result, 'issues'):
                    for issue in result.issues:
                        validation_errors_total.labels(
                            agent=validator_name,
                            severity=issue.severity
                        ).inc()
                
                if hasattr(result, 'records_processed'):
                    validation_records_processed.labels(
                        validator=validator_name
                    ).inc(result.records_processed)
                
                return result
                
            except Exception as e:
                validation_errors_total.labels(
                    agent=validator_name,
                    severity="critical"
                ).inc()
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Decorator for tracking API metrics
def track_api_metrics(endpoint: str):
    """
    Decorator to track API endpoint metrics.
    
    Usage:
        @track_api_metrics("/api/v1/validate")
        async def validate_endpoint(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            
            try:
                result = await func(*args, **kwargs)
                return result
                
            except Exception as e:
                status_code = 500
                raise
                
            finally:
                duration = time.time() - start_time
                
                api_requests_total.labels(
                    method="POST",  # Would extract from request
                    endpoint=endpoint,
                    status_code=str(status_code)
                ).inc()
                
                api_request_duration_seconds.labels(
                    method="POST",
                    endpoint=endpoint
                ).observe(duration)
        
        return wrapper
    return decorator


# Context manager for tracking active validations
class ValidationTracker:
    """Context manager for tracking active validations"""
    
    def __enter__(self):
        active_validations.inc()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        active_validations.dec()


# Function to record external API call
def record_external_api_call(
    provider: str,
    endpoint: str,
    duration: float,
    status: str,
    batch_size: int = 1
):
    """
    Record external API call metrics.
    
    Args:
        provider: API provider (ncbi, ensembl, etc.)
        endpoint: API endpoint called
        duration: Call duration in seconds
        status: Call status (success, error, timeout)
        batch_size: Number of items in batch
    """
    external_api_calls_total.labels(
        provider=provider,
        endpoint=endpoint,
        status=status
    ).inc()
    
    external_api_duration_seconds.labels(
        provider=provider,
        endpoint=endpoint
    ).observe(duration)
    
    if batch_size > 1:
        external_api_batch_size.labels(
            provider=provider
        ).observe(batch_size)