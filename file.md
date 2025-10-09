# Bio Data Validation System - File Documentation

This document describes every file in the bio_data_validation system, organized by directory.

---

## Root Directory

Project configuration and utility files.

### `Makefile`
Build automation and task runner with commands for:
- Dependency installation (install, install-dev)
- Test execution (test, test-unit, test-integration, test-e2e, test-system, test-all)
- Code quality (lint, format, test-cov)
- Docker operations (docker-build)
- CI/CD helpers (pre-commit, ci)
- Cleanup and requirements export

### `README.md`
Project documentation and overview. Contains project description, setup instructions, and usage examples.

### `pyproject.toml`
Poetry project configuration file defining:
- Project metadata (name, version, description, authors)
- Python dependencies (pydantic, pandas, biopython, fastapi, etc.)
- Development dependencies (pytest, black, mypy, etc.)
- Tool configurations (black, isort, mypy, pytest, coverage)
- Build system settings

### `poetry.lock`
Poetry dependency lock file ensuring reproducible builds. Auto-generated from pyproject.toml dependencies.

### `requirements.txt`
Production requirements exported from Poetry for compatibility with pip-based workflows. Generated via `make export-reqs`.

### `requirements-dev.txt`
Development and testing requirements exported from Poetry. Includes production requirements plus testing and linting tools.

### `docker-compose.yml`
Docker Compose orchestration for complete monitoring stack:
- Bio-validation API service (port 8000)
- Prometheus metrics collection (port 9090)
- Grafana visualization (port 3000)
- Volume management for persistent data
- Health checks and restart policies

### `check_ncbi_key.py`
Utility script to verify NCBI API key configuration:
- Loads and validates NCBI_API_KEY from .env file
- Displays key status and rate limit information
- Helps troubleshoot API authentication issues

### `real_world_validation_test.py`
Comprehensive end-to-end validation test script:
- Creates realistic guide RNA datasets with various quality issues
- Runs complete validation workflow through orchestrator
- Generates colored terminal output with validation results
- Saves reports in JSON, CSV, and Markdown formats
- Demonstrates production usage patterns

### `test_validator_diagnostics.py`
Diagnostic test script for validator detection logic:
- Tests duplicate sequence detection
- Tests poly-T stretch detection
- Tests guide length validation
- Tests class imbalance detection
- Tests missing value bias detection
- Useful for debugging individual validator components

### `debug_output.txt`
Debug output file for troubleshooting (should be in .gitignore).

### `file.md`
This documentation file - comprehensive listing of all project files with descriptions.

**Note:** `requirements.text` appears to be a duplicate/typo of `requirements.txt` and should potentially be removed or renamed.

---

## config/

Configuration files for the validation system.

### `config/base_config.py`
Defines the main application settings using Pydantic BaseSettings. Includes configuration for:
- Application metadata (name, version, environment)
- Database connection URLs
- External API settings (NCBI, Ensembl)
- API rate limiting parameters
- MLFlow tracking configuration
- Monitoring and logging settings
- Policy engine paths

### `config/policy_config.yml`
YAML configuration file defining validation decision policies:
- Decision matrix with thresholds for critical/error/warning counts
- Human review trigger conditions
- Policy rules for automated accept/reject decisions
- Validation workflow stages and their execution order
- Decision rationale templates

### `config/validation_rules.yml`
YAML file containing data quality validation rules:
- Consistency checks (required columns, data types, value ranges)
- Cross-column validation rules
- Duplicate detection settings
- Bias detection thresholds
- Custom validation rules

---

## infrastructure/docker/

Docker infrastructure for containerized deployment.

### `infrastructure/docker/Dockerfile`
Multi-stage Docker build configuration:
- Builder stage: installs Poetry and dependencies
- Runtime stage: creates minimal production image
- Security: runs as non-root user
- Health check endpoint configuration
- Exposes port 8000 for API access

---

## infrastructure/prometheus/

Prometheus monitoring and alerting configuration.

### `infrastructure/prometheus/prometheus.yml`
Prometheus server configuration:
- Global scrape settings (15s intervals)
- Scrape targets for bio-validation API
- Alert rule file references
- Service discovery for Docker Compose
- Prometheus self-monitoring

### `infrastructure/prometheus/alerts.yml`
Comprehensive Prometheus alerting rules:
- **API Health**: API down, high error rate, slow responses
- **Validation Performance**: High failure rates, timeouts, slow processing
- **External APIs**: NCBI API errors, rate limiting, slow responses
- **Data Quality**: Critical issues, duplicates, validator failures
- **Human Review**: Queue backlog alerts
- **System Resources**: Memory and CPU usage warnings
- **Business Logic**: No validations, unusual volume, all rejections
- Severity levels: critical, warning, info
- Detailed annotations and recommended actions

---

## scripts/examples/

Example scripts demonstrating system usage.

### `scripts/examples/__init__.py`
Empty init file for Python package structure.

### `scripts/examples/example_usage.py`
Example scripts showing how to use the validation system for common tasks like validating CRISPR guide RNAs and biological sequences.

---

## scripts/metrics/

Scripts for calculating and tracking data quality metrics.

### `scripts/metrics/__init__.py`
Empty init file for Python package structure.

### `scripts/metrics/calculate_quality_metrics.py`
Analyzes validation results to calculate comprehensive quality metrics:
- Decision distribution (accepted/rejected/conditional)
- Stage-by-stage pass/fail rates
- Issue counts by severity level
- Execution time statistics
- Success rate calculations
- Outputs metrics in JSON format

### `scripts/metrics/push_to_mlflow.py`
Pushes validation metrics and results to MLFlow for experiment tracking and model monitoring.

---

## scripts/setup/

Setup and initialization scripts.

### `scripts/setup/init_dvc.py`
Initializes DVC (Data Version Control) for tracking datasets and model artifacts.

---

## scripts/validation/

Scripts for running validation workflows and generating reports.

### `scripts/validation/__init__.py`
Empty init file for Python package structure.

### `scripts/validation/check_status.py`
Checks the status of running or completed validation jobs.

### `scripts/validation/generate_report.py`
Generates human-readable validation reports from validation results:
- Creates markdown-formatted reports with decision summaries
- Lists issues by stage and severity
- Includes icons for visual clarity (✅ ❌ ⚠️)
- Can output in markdown or HTML format

### `scripts/validation/validate_datasets.py`
Batch validation script for processing multiple datasets through the validation pipeline.

---

## src/

Source code for the validation system.

### `src/__init__.py`
Source package initialization module:
- Imports monitoring setup
- Initializes structured logging
- Configures log level and format from settings
- Called automatically on application startup

---

## src/agents/

AI agent components for orchestration and human-in-the-loop workflows.

### `src/agents/__init__.py`
Empty init file for Python package structure.

### `src/agents/orchestrator.py`
The main validation orchestrator that coordinates the entire validation workflow:
- Manages validation stages (schema → rules → biological checks)
- Implements short-circuiting to stop on critical failures
- Supports parallel execution of biological validators
- Integrates with PolicyEngine for final decisions
- Coordinates human review when needed
- Returns comprehensive validation reports

### `src/agents/human_review_coordinator.py`
Manages human-in-the-loop review processes with active learning:
- Prioritizes issues for human review by severity
- Routes issues to appropriate experts (biologists, data engineers)
- Uses active learning to select most informative issues
- Learns from human feedback to improve future decisions
- Can auto-resolve issues with high confidence based on patterns
- Tracks expert performance and review metrics

---

## src/api/

FastAPI REST API for validation services.

### `src/api/__init__.py`
Empty init file for Python package structure.

### `src/api/models.py`
Pydantic models for API request/response validation:
- Request models: ValidationRequest, FileUploadRequest, BatchValidationRequest
- Response models: ValidationStatusResponse, ValidationReportResponse, MetricsResponse
- Enums: ValidationFormat, ValidationStatus, Decision
- Error response models

### `src/api/routes.py`
FastAPI route definitions for the validation API:
- POST `/api/v1/validate` - Submit dataset for validation
- GET `/api/v1/validate/{id}` - Get validation status and results
- POST `/api/v1/validate/file` - Upload and validate file
- POST `/api/v1/validate/batch` - Batch validation
- GET `/api/v1/metrics` - System metrics
- GET `/health` - Health check endpoint

---

## src/engine/

Policy engine for making automated validation decisions.

### `src/engine/__init__.py`
Empty init file for Python package structure.

### `src/engine/policy_engine.py`
Policy-based decision engine that applies configurable rules:
- Loads policy configuration from YAML or dict
- Counts issues by severity across all validation stages
- Applies decision matrix to determine accept/reject/conditional
- Determines if human review should be triggered
- Generates human-readable decision rationales
- Supports custom conditions for conditional acceptance

### `src/engine/decision_tables.py`
Programmatic decision table implementation:
- Defines decision rules with priorities
- Threshold configuration for severity levels
- Review trigger configuration
- Rule evaluation engine with safe expression evaluation
- Pre-configured decision table presets (strict, lenient, production)

---

## src/monitoring/

Monitoring, logging, and metrics collection.

### `src/monitoring/__init__.py`
Empty init file for Python package structure.

### `src/monitoring/logging_config.py`
Centralized logging configuration with structured logging:
- JSON formatter for machine-readable logs
- Context filter for adding metadata
- Rotating file handlers
- Console and file output
- LogContext manager for contextual logging

### `src/monitoring/metrics.py`
Prometheus metrics definitions and tracking:
- Validation metrics (requests, duration, errors)
- API metrics (request counts, response times)
- External API metrics (NCBI/Ensembl call tracking)
- Data quality metrics (issues detected, duplicates)
- Decorators for automatic metric collection
- Context managers for active validation tracking

---

## src/schemas/

Pydantic schemas and data models.

### `src/schemas/__init__.py`
Empty init file for Python package structure.

### `src/schemas/base_schemas.py`
Core schema definitions used throughout the system:
- SerializableEnum: Base class for enums with automatic JSON serialization
- ConfigurableComponent: Base class for components with flexible configuration
- Enums: ValidationSeverity, Decision, ValidationStatus, FormatType, ReviewPriority, ReviewStatus
- Models: ValidationIssue, ValidationResult, DatasetMetadata, ValidationReport, ReviewTask
- Utility functions: serialize_for_json, deserialize_enum

### `src/schemas/biological_schemas.py`
Pydantic schemas for biological data validation:
- SequenceRecord: Generic biological sequence schema with type validation
- GuideRNARecord: CRISPR guide RNA schema with PAM validation
- Validates sequence alphabets (DNA/RNA/protein)
- Enforces nuclease-specific PAM patterns

---

## src/utils/

Utility functions and helper classes.

### `src/utils/__init__.py`
Empty init file for Python package structure.

### `src/utils/batch_processor.py`
Utility for processing items in batches with rate limiting:
- Configurable batch sizes and rate limits
- Automatic retry logic with exponential backoff
- Used for external API calls to avoid rate limiting
- Supports async processing

### `src/utils/bio_tools.py`
Bioinformatics utility functions:
- GC content calculation
- DNA/RNA/protein sequence validation
- Reverse complement generation
- Sequence translation
- PAM sequence detection
- Melting temperature calculation
- Restriction site finding
- Off-target checking (placeholder)

### `src/utils/database_clients.py`
SQLAlchemy database client for storing validation results:
- Models: ValidationRun, ValidationIssue, HumanReview
- DatabaseClient class with methods for saving and querying validation data
- Handles flexible constructor arguments for backward compatibility
- Avoids SQLAlchemy reserved words (metadata → dataset_metadata)

---

## src/validators/

Validation implementations for different validation stages.

### `src/validators/__init__.py`
Empty init file for Python package structure.

### `src/validators/schema_validator.py`
Schema validation using Pydantic and BioPython:
- Validates FASTA format files
- Validates guide RNA records against GuideRNARecord schema
- Validates JSON structure
- Validates tabular data (DataFrames)
- Detects missing required fields, type mismatches, and schema violations

### `src/validators/rule_validator.py`
Vectorized rule-based validation using pandas:
- Consistency checks: required columns, data types, value ranges, cross-column rules
- Duplicate detection: exact and near-duplicate sequences
- Bias detection: class imbalance, missing value patterns, distribution skewness
- Custom rule evaluation
- Highly optimized with vectorized operations

### `src/validators/bio_rules.py`
Local biological plausibility checks without external APIs:
- Guide length validation (critical and suboptimal ranges)
- PAM sequence validation for different nucleases
- GC content checks
- Invalid DNA character detection
- Poly-T stretch detection
- Homopolymer run detection
- RNA/DNA base confusion detection
- All checks are vectorized for performance

### `src/validators/bio_lookups.py`
External database validation with batching and rate limiting:
- Gene symbol validation against NCBI Gene database
- Protein ID validation against NCBI Protein database
- Batch processing with configurable batch sizes
- Rate limiting to comply with API restrictions
- Async implementation for performance
- Detects invalid and ambiguous identifiers

---

## tests/

Test suite with unit, integration, and end-to-end tests.

### `tests/conftest.py`
Pytest configuration and shared fixtures:
- Test data fixtures (valid/invalid guide RNAs, large datasets)
- Metadata factories
- Mock API responses (NCBI, Ensembl)
- Database fixtures (in-memory SQLite)
- Assertion helpers for validation results
- Cleanup fixtures
- Test markers (integration, e2e, slow, api)

### `tests/builders.py`
Builder pattern implementations for creating test objects programmatically.

### `tests/README.md`
Documentation for the test suite structure and running tests.

### `tests/pytest.ini`
Pytest configuration file with test discovery and plugin settings.

---

## tests/unit/agents/

Unit tests for agent components.

### `tests/unit/agents/test_orchestrator.py`
Tests for the ValidationOrchestrator:
- Workflow orchestration
- Short-circuiting behavior
- Parallel execution
- Error handling

### `tests/unit/agents/test_human_review_coordinator.py`
Tests for HumanReviewCoordinator:
- Issue prioritization
- Expert routing
- Active learning
- Feedback capture and pattern learning

---

## tests/unit/validators/

Unit tests for validator components.

### `tests/unit/validators/test_schema_validator.py`
Tests for schema validation:
- FASTA format validation
- Guide RNA schema validation
- Error detection and reporting

### `tests/unit/validators/test_rule_validator.py`
Tests for rule-based validation:
- Consistency checks
- Duplicate detection
- Bias detection
- Custom rules

### `tests/unit/validators/test_bio_rules.py`
Tests for biological rules validation:
- Guide length checks
- PAM validation
- GC content checks
- Sequence quality checks

### `tests/unit/validators/test_bio_lookups.py`
Tests for external database lookups:
- Mock NCBI API responses
- Batch processing
- Error handling

---

## tests/unit/engine/

Unit tests for policy engine.

### `tests/unit/engine/test_policy_engine.py`
Tests for PolicyEngine:
- Decision matrix evaluation
- Human review triggers
- Rationale generation

---

## tests/integration/

Integration tests for multi-component workflows.

### `tests/integration/test_integration_workflow.py`
Tests the complete validation workflow with multiple validators working together.

### `tests/integration/test_api_integration.py`
Tests API endpoints with real validation workflows.

### `tests/integration/test_database_integration.py`
Tests database integration with validation persistence.

---

## tests/e2e/

End-to-end tests for complete system validation.

### `tests/e2e/test_complete_workflow.py`
End-to-end test of the entire validation pipeline from API request to database storage.

### `tests/e2e/test_api_endpoints.py`
Tests all API endpoints with realistic data and workflows.

---

## tests/system/

System-level test scripts.

### `tests/system/test_e2e_workflow.sh`
Bash script for end-to-end system testing.

### `tests/system/test_components.sh`
Bash script for testing individual system components.

---

## validation_output/

Output directory for validation reports (generated).

### `validation_output/crispr_validation_report.json`
JSON format validation report for CRISPR guide RNA dataset.

### `validation_output/crispr_validation_report_data.csv`
CSV format detailed validation data.

### `validation_output/crispr_validation_report_summary.md`
Markdown format human-readable summary report.

---

## Summary

The bio_data_validation system is a comprehensive, production-grade validation framework for biological data with:

- **Multi-stage validation**: Schema → Rules → Biological checks
- **AI agents**: Orchestration and human-in-the-loop coordination
- **Policy-based decisions**: Configurable thresholds and rules
- **External integrations**: NCBI and Ensembl database validation
- **REST API**: Full-featured FastAPI service
- **Monitoring**: Prometheus metrics, alerting, and structured logging
- **Database**: SQLAlchemy-based persistence
- **Testing**: Comprehensive unit, integration, e2e, and system test coverage
- **Docker**: Production-ready containerization with Docker Compose orchestration
- **Build automation**: Makefile with commands for testing, linting, and CI/CD
- **Dependency management**: Poetry with pip-compatible requirements export
- **Diagnostic tools**: Real-world validation tests and validator diagnostics

All components are designed with performance, reliability, and maintainability in mind.

### Project Structure Overview

```
bio_data_validation/
├── Root configuration (Makefile, pyproject.toml, docker-compose.yml)
├── config/ (application and validation settings)
├── infrastructure/ (Docker and Prometheus configurations)
├── scripts/ (example usage, metrics, setup, and validation scripts)
├── src/ (core validation system)
│   ├── agents/ (orchestration and human review)
│   ├── api/ (FastAPI REST endpoints)
│   ├── engine/ (policy and decision tables)
│   ├── monitoring/ (logging and metrics)
│   ├── schemas/ (Pydantic data models)
│   ├── utils/ (batch processing, bio tools, database clients)
│   └── validators/ (schema, rule, bio-rule, and bio-lookup validators)
├── tests/ (unit, integration, e2e, and system tests)
└── validation_output/ (generated validation reports)
```
