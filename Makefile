# mt5linux Makefile
# Poetry-based build with strict quality gates

.PHONY: setup lint format type test coverage check validate clean help

# Use workspace venv poetry
VENV_BIN ?= $(shell dirname $(shell which python 2>/dev/null || echo "../../.venv/bin/python"))
POETRY ?= $(VENV_BIN)/poetry

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install with Poetry (all groups, all extras)
	$(POETRY) lock --quiet 2>/dev/null || $(POETRY) lock
	$(POETRY) install --all-groups --all-extras

lint: ## Run ruff linting
	$(POETRY) run ruff check mt5linux/ tests/
	$(POETRY) run ruff format --check mt5linux/ tests/

format: ## Format code with ruff
	$(POETRY) run ruff format mt5linux/ tests/
	$(POETRY) run ruff check --fix mt5linux/ tests/

type: ## Type checking (mypy --strict)
	$(POETRY) run mypy mt5linux/ tests/ --strict

test: ## Run tests (auto-starts docker container)
	$(POETRY) run pytest tests/ -v --tb=short

coverage: ## Run tests with 100% coverage requirement
	$(POETRY) run pytest tests/ -v --cov=mt5linux --cov-report=term-missing --cov-fail-under=100

check: lint type ## Quick check (lint + type)
	@echo "✅ Check passed"

validate: lint type coverage ## Full validation (lint + type + coverage 100%)
	@echo "✅ Validation passed"

clean: ## Remove cache directories
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ .coverage
	rm -rf mt5linux/__pycache__ tests/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
