.PHONY: help install install-dev test test-cov lint lint-all format format-check typecheck clean all docs docs-serve build publish coverage

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

install-dev: ## Install in development mode with all dev dependencies
	pip install -e ".[dev]"
	uv run --with pre-commit pre-commit install

test: ## Run all tests
	@echo "Running tests for all packages..."
	@for pkg in pi_ai pi_agent_core pi_coding_agent pi_mom pi_pods pi_tui pi_web_ui; do \
		if [ -d "packages/$$pkg/tests" ]; then \
			echo "\n=== Testing $$pkg ==="; \
			cd "packages/$$pkg" && uv run --with pytest --with pytest-asyncio pytest tests/ -v 2>&1 | tail -20 || true; \
			cd ../..; \
		fi \
	done

test-cov: ## Run tests with coverage (terminal + HTML report)
	@echo "Running tests with coverage..."
	pytest packages/ -v --cov=packages --cov-report=term-missing --cov-report=html || true

lint: ## Run ruff linter
	uv run --with ruff ruff check packages/

lint-all: ## Run all linters (ruff + mypy)
	uv run --with ruff --with mypy sh -c 'ruff check packages/ && mypy packages/'

format: ## Auto-format code with ruff
	uv run --with ruff ruff format packages/

format-check: ## Check code formatting without making changes
	uv run --with ruff --with black sh -c 'ruff format --check packages/ && black --check packages/'

typecheck: ## Run type checking with mypy
	uv run --with mypy mypy packages/

coverage: ## Generate coverage report
	uv run --with pytest --with pytest-cov pytest packages/ -v --cov=packages --cov-report=term --cov-report=html --cov-report=xml

all: format lint typecheck test ## Run format, lint, typecheck, and test

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf coverage.xml
	find packages -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find packages -type f -name "*.pyc" -delete
	docker-compose -f docker-compose.dev.yml down --volumes --remove-orphans 2>/dev/null || true

docs: ## Build documentation
	uv run --with mkdocs --with mkdocs-material --with mkdocstrings mkdocs build

docs-serve: ## Serve documentation locally
	uv run --with mkdocs --with mkdocs-material --with mkdocstrings mkdocs serve

build: ## Build packages
	uv run --with build python -m build

publish-test: ## Publish to TestPyPI
	uv run --with twine python -m twine upload --repository testpypi dist/*

publish: ## Publish to PyPI
	uv run --with twine python -m twine upload dist/*

# Package-specific commands
agent-core: ## Run agent core package
	python -m pi_agent_core

web-ui: ## Run web UI
	python -m pi_web_ui

tui: ## Run TUI
	python -m pi_tui

coding-agent: ## Run coding agent
	python -m pi_coding_agent
