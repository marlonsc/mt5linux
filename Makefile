# mt5linux Makefile
# Poetry-based build with all groups and extras

.PHONY: setup lint format test check help

# Use workspace venv poetry
VENV_BIN ?= $(shell dirname $(shell which python 2>/dev/null || echo "../../.venv/bin/python"))
POETRY ?= $(VENV_BIN)/poetry

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Install with Poetry (all groups, all extras)
	$(POETRY) lock --quiet 2>/dev/null || $(POETRY) lock
	$(POETRY) install --all-groups --all-extras

lint: ## Run linting
	$(POETRY) run ruff check .

format: ## Format code
	$(POETRY) run ruff format .

test: ## Run tests
	$(POETRY) run pytest -v

check: lint ## Quick check
	@echo "✅ Check passed"
