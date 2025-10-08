# Makefile

.PHONY: help install install-dev test lint format clean docker-build

help:
	@echo "Available commands:"
	@echo "  make install         - Install production dependencies"
	@echo "  make install-dev     - Install all dependencies including dev"
	@echo "  make test           - Run all pytest tests"
	@echo "  make test-unit      - Run unit tests only (fast)"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-e2e       - Run end-to-end tests"
	@echo "  make test-system    - Run system bash tests"
	@echo "  make test-all       - Run ALL tests (pytest + system)"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo "  make test-quick     - Run quick tests (no slow markers)"
	@echo "  make test-failed    - Re-run only failed tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make export-reqs    - Export requirements.txt from Poetry"

install:
	poetry install --no-dev

install-dev:
	poetry install
	poetry run pre-commit install

test:
	poetry run pytest tests/ -v

test-cov:
	poetry run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "📊 Coverage report generated: htmlcov/index.html"

test-unit:
	poetry run pytest tests/unit/ -v

test-integration:
	poetry run pytest tests/integration/ -v -m integration

test-e2e:
	poetry run pytest tests/e2e/ -v -m e2e

test-performance:
	poetry run pytest tests/performance/ -v -m performance

# NEW: Run system bash tests
test-system:
	@echo "🔧 Running system component tests..."
	@bash tests/system/test_components.sh
	@echo "🔧 Running system E2E workflow tests..."
	@bash tests/system/test_e2e_workflow.sh
	@echo "✅ System tests complete!"

# NEW: Run ALL tests (pytest + system)
test-all: test test-system
	@echo "✅ All test suites complete!"

# NEW: Run quick tests (skip slow markers)
test-quick:
	poetry run pytest tests/unit/ -v -m "not slow"

# NEW: Re-run only failed tests from last run
test-failed:
	poetry run pytest --lf -v

# NEW: Run tests with verbose debugging
test-debug:
	poetry run pytest tests/ -vv --showlocals --tb=long

# NEW: Run specific test file (usage: make test-file FILE=tests/unit/test_something.py)
test-file:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Usage: make test-file FILE=tests/unit/test_something.py"; \
		exit 1; \
	fi
	poetry run pytest $(FILE) -vv

# NEW: Watch mode for TDD (requires pytest-watch)
test-watch:
	poetry run ptw tests/ -- -v

lint:
	poetry run black --check src tests
	poetry run isort --check-only src tests
	poetry run flake8 src tests
	poetry run mypy src

format:
	poetry run black src tests
	poetry run isort src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build

export-reqs:
	poetry export -f requirements.txt --output requirements.txt --without-hashes
	poetry export -f requirements.txt --output requirements-dev.txt --with dev --without-hashes

docker-build:
	docker build -t bio-data-validation:latest -f infrastructure/docker/Dockerfile .

dvc-setup:
	poetry run python scripts/setup/init_dvc.py

setup: install-dev dvc-setup
	@echo "✅ Setup complete! Run 'make test' to verify installation."

# NEW: Quick validation before commit
pre-commit: format lint test-quick
	@echo "✅ Pre-commit checks passed!"

# NEW: CI simulation - runs what CI will run
ci: lint test-cov
	@echo "✅ CI simulation complete!"