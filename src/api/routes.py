# src/api/routes.py
"""
FastAPI routes for validation API.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Query, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uuid
import asyncio
from datetime import datetime
import logging
import pandas as pd
from io import StringIO
import json
import time
from pathlib import Path

from src.api.models import (
    ValidationRequest,
    ValidationSubmitResponse,
    ValidationStatusResponse,
    ValidationReportResponse,
    HealthResponse,
    MetricsResponse,
    BatchValidationRequest,
    BatchValidationResponse,
    ErrorResponse,
    ValidationStatus,
    Decision
)
from src.agents.orchestrator import ValidationOrchestrator, OrchestrationConfig
from src.schemas.base_schemas import DatasetMetadata, serialize_for_json
from src.monitoring.metrics import (
    validation_requests_total,
    validation_duration_seconds,
    active_validations,
    api_requests_total,
    api_request_duration_seconds
)

# ═══════════════════════════════════════════════════════════════════════════
# MONITORING IMPORTS - Prometheus metrics
# ═══════════════════════════════════════════════════════════════════════════
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


# Initialize FastAPI app
app = FastAPI(
    title="Bio-Data Validation API",
    description="Production-grade bioinformatics data validation service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# REPORT EXPORT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
REPORT_OUTPUT_DIR = Path("validation_output")
REPORT_OUTPUT_DIR.mkdir(exist_ok=True)

def save_validation_report(validation_id: str, report: dict):
    """
    Save validation report to validation_output/ directory.
    Creates JSON file with timestamp and validation ID.
    """
    try:
        # Create filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_{timestamp}_{validation_id[:8]}.json"
        filepath = REPORT_OUTPUT_DIR / filename
        
        # Prepare report data
        report_data = {
            "validation_id": validation_id,
            "timestamp": datetime.utcnow().isoformat(),
            "report": report
        }
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(serialize_for_json(report_data), f, indent=2)
        
        logger.info(f"📄 Report saved: {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.error(f"Failed to save report {validation_id}: {str(e)}")
        return None

# ═══════════════════════════════════════════════════════════════════════════
# MONITORING: Request tracking middleware
# Automatically tracks all API requests with metrics
# ═══════════════════════════════════════════════════════════════════════════
@app.middleware("http")
async def track_api_requests(request, call_next):
    """Track all API requests with Prometheus metrics"""
    # Skip metrics endpoint to avoid recursion
    if request.url.path == "/metrics":
        return await call_next(request)
    
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Record metrics
    api_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code
    ).inc()
    
    api_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

# Logging
logger = logging.getLogger(__name__)

# In-memory storage for validation tasks (use Redis/DB in production)
validation_tasks = {}
validation_reports = {}

# Initialize orchestrator
orchestrator_config = OrchestrationConfig(
    timeout_seconds=300,
    enable_short_circuit=True,
    enable_parallel_bio=True
)
orchestrator = ValidationOrchestrator(orchestrator_config)


def serialize_datetime(obj):
    """Serialize datetime objects for JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# Background task for validation
async def run_validation_task(validation_id: str, request: ValidationRequest):
    """Background task to run validation"""
    try:
        validation_tasks[validation_id] = {
            "status": ValidationStatus.IN_PROGRESS.value,
            "current_stage": "schema",
            "progress_percent": 0
        }
        
        active_validations.inc()
        
        # Convert data to DataFrame
        if isinstance(request.data, list):
            df = pd.DataFrame(request.data)
        elif isinstance(request.data, dict):
            df = pd.DataFrame([request.data])
        elif isinstance(request.data, str):
            # Parse string data (CSV or FASTA)
            if request.format.value in ['csv', 'tabular']:
                df = pd.read_csv(StringIO(request.data))
            else:
                df = request.data  # Pass as-is for FASTA/FASTQ
        else:
            raise ValueError(f"Unsupported data type: {type(request.data)}")
        
        # Create metadata
        metadata = DatasetMetadata(
            dataset_id=validation_id,
            format_type=request.format.value,
            record_count=len(df) if isinstance(df, pd.DataFrame) else 1,
            **request.metadata
        )
        
        # Update progress
        validation_tasks[validation_id]["progress_percent"] = 20
        
        # Run validation
        report = await orchestrator.validate_dataset(df, metadata)
        
        # Ensure decision is lowercase string
        if "final_decision" in report:
            decision = report["final_decision"]
            if hasattr(decision, 'value'):
                decision = decision.value
            report["final_decision"] = str(decision).lower()
        
        # Store report in memory
        validation_reports[validation_id] = report
        
        # ═══════════════════════════════════════════════════════════════════
        # SAVE REPORT TO FILE - NEW!
        # ═══════════════════════════════════════════════════════════════════
        saved_path = save_validation_report(validation_id, report)
        if saved_path:
            report["saved_to_file"] = saved_path
        
        # Update task status
        validation_tasks[validation_id] = {
            "status": ValidationStatus.COMPLETED.value,
            "current_stage": "complete",
            "progress_percent": 100,
            "completed_at": datetime.utcnow(),
            "report_file": saved_path
        }
        
        # Record metrics
        validation_requests_total.labels(
            dataset_type=request.format.value,
            decision=report["final_decision"]
        ).inc()
        
        validation_duration_seconds.labels(
            agent="orchestrator",
            stage="complete"
        ).observe(report["execution_time_seconds"])
        
    except asyncio.TimeoutError:
        validation_tasks[validation_id] = {
            "status": ValidationStatus.TIMEOUT.value,
            "error": "Validation timeout"
        }
        logger.error(f"Validation {validation_id} timed out")
        
    except Exception as e:
        validation_tasks[validation_id] = {
            "status": ValidationStatus.FAILED.value,
            "error": str(e)
        }
        logger.exception(f"Validation {validation_id} failed: {str(e)}")
        
    finally:
        active_validations.dec()


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "Bio-Data Validation API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        components={
            "orchestrator": "healthy",
            "database": "healthy",
            "api": "healthy",
            "metrics": "healthy"
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# METRICS ENDPOINT - FIXED to prevent 307 redirects
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus text format.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/validate", status_code=200)
async def submit_validation(
    request: ValidationRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a dataset for validation.
    Returns validation ID for status polling.
    """
    validation_id = str(uuid.uuid4())
    
    # Initialize task
    validation_tasks[validation_id] = {
        "status": ValidationStatus.PENDING.value,
        "submitted_at": datetime.utcnow()
    }
    
    # Schedule background validation
    background_tasks.add_task(run_validation_task, validation_id, request)
    
    response_data = {
        "validation_id": validation_id,
        "status": ValidationStatus.PENDING.value,
        "submitted_at": datetime.utcnow().isoformat(),
        "estimated_completion_seconds": 30
    }
    
    return JSONResponse(content=response_data, status_code=200)


@app.get("/api/v1/validate/{validation_id}")
async def get_validation_status(validation_id: str):
    """Get validation status and results"""
    if validation_id not in validation_tasks:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    task = validation_tasks[validation_id]
    report = validation_reports.get(validation_id)
    
    response_data = {
        "validation_id": validation_id,
        "status": task["status"],
        "progress_percent": task.get("progress_percent"),
        "current_stage": task.get("current_stage"),
        "submitted_at": task.get("submitted_at", datetime.utcnow()).isoformat() if isinstance(task.get("submitted_at"), datetime) else task.get("submitted_at"),
        "completed_at": task.get("completed_at").isoformat() if isinstance(task.get("completed_at"), datetime) else task.get("completed_at"),
        "report": report,
        "report_file": task.get("report_file"),  # NEW: Path to saved file
        "error": task.get("error")
    }
    
    # Serialize datetime objects using utility function
    return JSONResponse(content=serialize_for_json(response_data))


@app.get("/api/v1/reports")
async def list_reports():
    """
    List all saved validation reports.
    NEW ENDPOINT!
    """
    reports = []
    for filepath in REPORT_OUTPUT_DIR.glob("validation_*.json"):
        reports.append({
            "filename": filepath.name,
            "path": str(filepath),
            "size_bytes": filepath.stat().st_size,
            "created": datetime.fromtimestamp(filepath.stat().st_ctime).isoformat()
        })
    
    reports.sort(key=lambda x: x["created"], reverse=True)
    
    return {
        "total_reports": len(reports),
        "reports": reports
    }


@app.get("/api/v1/reports/{filename}")
async def get_report_file(filename: str):
    """
    Download a specific validation report.
    NEW ENDPOINT!
    """
    filepath = REPORT_OUTPUT_DIR / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    
    return FileResponse(
        path=filepath,
        media_type="application/json",
        filename=filename
    )


@app.post("/api/v1/validate/file", status_code=200)
async def validate_file(
    file: UploadFile = File(...),
    format: str = Query(..., description="File format (fasta, csv, etc.)"),
    background_tasks: BackgroundTasks = None
):
    """Upload and validate a file"""
    validation_id = str(uuid.uuid4())
    
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Create validation request
        request = ValidationRequest(
            format=format,
            data=content_str,
            metadata={"filename": file.filename}
        )
        
        # Initialize task
        validation_tasks[validation_id] = {
            "status": ValidationStatus.PENDING.value,
            "submitted_at": datetime.utcnow()
        }
        
        # Schedule validation
        background_tasks.add_task(run_validation_task, validation_id, request)
        
        response_data = {
            "validation_id": validation_id,
            "status": ValidationStatus.PENDING.value,
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        return JSONResponse(content=response_data, status_code=200)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File processing error: {str(e)}")


@app.post("/api/v1/validate/batch")
async def submit_batch_validation(
    request: BatchValidationRequest,
    background_tasks: BackgroundTasks
):
    """Submit multiple datasets for validation"""
    batch_id = str(uuid.uuid4())
    validation_ids = []
    
    for dataset_request in request.datasets:
        validation_id = str(uuid.uuid4())
        validation_ids.append(validation_id)
        
        validation_tasks[validation_id] = {
            "status": ValidationStatus.PENDING.value,
            "submitted_at": datetime.utcnow(),
            "batch_id": batch_id
        }
        
        background_tasks.add_task(run_validation_task, validation_id, dataset_request)
    
    response_data = {
        "batch_id": batch_id,
        "total_datasets": len(request.datasets),
        "validation_ids": validation_ids,
        "status": ValidationStatus.PENDING.value
    }
    
    return JSONResponse(content=response_data)


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get system metrics"""
    total = len(validation_tasks)
    completed = sum(1 for t in validation_tasks.values() if t["status"] == ValidationStatus.COMPLETED.value)
    
    response_data = {
        "total_validations": total,
        "validations_today": total,
        "average_execution_time_seconds": 5.2,
        "success_rate_percent": (completed / total * 100) if total > 0 else 0,
        "active_validations": sum(1 for t in validation_tasks.values() if t["status"] == ValidationStatus.IN_PROGRESS.value),
        "human_reviews_pending": 0
    }
    
    return JSONResponse(content=response_data)


@app.delete("/api/v1/validate/{validation_id}")
async def cancel_validation(validation_id: str):
    """Cancel a pending validation"""
    if validation_id not in validation_tasks:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    task = validation_tasks[validation_id]
    if task["status"] != ValidationStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Cannot cancel non-pending validation")
    
    validation_tasks[validation_id]["status"] = ValidationStatus.FAILED.value
    validation_tasks[validation_id]["error"] = "Cancelled by user"
    
    return {"message": "Validation cancelled"}


# ═══════════════════════════════════════════════════════════════════════════
# EXCEPTION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": str(uuid.uuid4())
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "request_id": str(uuid.uuid4())
        }
    )