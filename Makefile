# Makefile

.PHONY: help install install-dev test lint format clean docker-build

help:
	@echo "Available commands:"
	@echo "  make install         - Install production dependencies"
	@echo "  make install-dev     - Install all dependencies including dev"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage report"
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
	poetry run pytest tests/ --cov=src --cov-report=html --cov-report=term

test-unit:
	poetry run pytest tests/unit/ -v

test-integration:
	poetry run pytest tests/integration/ -v -m integration

test-e2e:
	poetry run pytest tests/e2e/ -v -m e2e

test-performance:
	poetry run pytest tests/performance/ -v -m performance

lint:
	poetry run black --check src tests
	poetry run isort --check-only src tests
	poetry run flake8 src tests
	poetry run mypy src

format:
	poetry run black src tests
	poetry run isort src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
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