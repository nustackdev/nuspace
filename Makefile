.PHONY: help install sync dev test lint format check clean clean-all web-install web-dev web-build build-nuspace build-ui build-all ci

BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

UI_APP := ts

help:
	@echo "$(BLUE)nuspace$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  make install         Install uv if needed"
	@echo "  make sync            Sync workspace (install all extras)"
	@echo "  make dev             Full dev setup (sync + pre-commit)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make test            Run all tests"
	@echo "  make test-cov        Run tests with coverage"
	@echo "  make test-fast       Run tests (fail fast)"
	@echo ""
	@echo "$(GREEN)Code Quality:$(NC)"
	@echo "  make lint            Check code with ruff"
	@echo "  make format          Format code with ruff"
	@echo "  make check           Run format-check + lint"
	@echo ""
	@echo "$(GREEN)nuspace-ui web:$(NC)"
	@echo "  make web-install     npm install in the ui workspace"
	@echo "  make web-dev         Run vite dev server"
	@echo "  make web-build       Build the vite bundle into $(UI_APP)/dist"
	@echo ""
	@echo "$(GREEN)Packages:$(NC)"
	@echo "  make build-nuspace   Build the nuspace wheel"
	@echo "  make build-ui        Build the nuspace-ui web-bundle wheel"
	@echo "  make build-all       Build both wheels"
	@echo ""
	@echo "$(GREEN)Cleanup:$(NC)"
	@echo "  make clean           Remove build artifacts"
	@echo "  make clean-all       Remove everything including .venv"

install:
	@command -v uv >/dev/null 2>&1 || { \
		echo "$(BLUE)Installing uv...$(NC)"; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	}
	@echo "$(GREEN)uv ready$(NC)"

sync: install
	@echo "$(BLUE)Syncing workspace...$(NC)"
	uv sync --all-extras
	@echo "$(GREEN)Workspace synced$(NC)"

dev: sync
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	uv run pre-commit install
	@echo "$(GREEN)Dev environment ready$(NC)"

test:
	@echo "$(BLUE)Running all tests...$(NC)"
	uv run pytest

test-cov:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	uv run pytest --cov --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)Report: reports/coverage/index.html$(NC)"

test-fast:
	@echo "$(BLUE)Running fast tests...$(NC)"
	uv run pytest -m "not slow" -x

lint:
	@echo "$(BLUE)Linting...$(NC)"
	uv run ruff check .

format:
	@echo "$(BLUE)Formatting...$(NC)"
	uv run ruff format .
	uv run ruff check --fix .
	@echo "$(GREEN)Done$(NC)"

format-check:
	@echo "$(BLUE)Checking format...$(NC)"
	uv run ruff format --check .

check: format-check lint
	@echo "$(GREEN)All checks passed$(NC)"

web-install:
	@echo "$(BLUE)Installing ui deps...$(NC)"
	cd $(UI_APP) && npm install
	@echo "$(GREEN)Installed$(NC)"

web-dev:
	@echo "$(BLUE)Starting vite dev server...$(NC)"
	cd $(UI_APP) && npm run dev

web-build:
	@echo "$(BLUE)Building nuspace-ui web bundle...$(NC)"
	cd $(UI_APP) && npm run build
	@echo "$(GREEN)Built: $(UI_APP)/dist/$(NC)"

build-nuspace:
	@echo "$(BLUE)Building nuspace wheel...$(NC)"
	uv build --wheel
	@echo "$(GREEN)Built: dist/$(NC)"

build-ui: web-build
	@echo "$(BLUE)Building nuspace-ui web-bundle wheel...$(NC)"
	# --out-dir keeps the wheel out of dist/, which IS the vite output we
	# force-include into it. Writing there packages the last wheel into the next.
	cd $(UI_APP) && uv build --wheel --out-dir wheel-dist
	@echo "$(GREEN)Built: $(UI_APP)/wheel-dist/$(NC)"

build-all: build-nuspace build-ui
	@echo "$(GREEN)Both wheels built$(NC)"

clean:
	@echo "$(BLUE)Cleaning...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ reports/
	@echo "$(GREEN)Clean$(NC)"

clean-all: clean
	@echo "$(BLUE)Removing .venv...$(NC)"
	rm -rf .venv/
	@echo "$(GREEN)Deep clean$(NC)"

ci: check test-cov
	@echo "$(GREEN)CI passed$(NC)"
