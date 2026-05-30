.PHONY: install dev test eval lint seed type-check clean

AGENT_DIR = services/agent
WEB_DIR   = apps/web
PYTHON    = python3.11

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	cd $(AGENT_DIR) && pip install -e ".[dev]"
	cd $(WEB_DIR)   && npm install

# ── Dev servers ───────────────────────────────────────────────────────────────
dev:
	@echo "Starting agent (port 8000) and web (port 3000)..."
	cd $(AGENT_DIR) && uvicorn api.main:app --reload --port 8000 &
	cd $(WEB_DIR)   && npm run dev

# ── Test ──────────────────────────────────────────────────────────────────────
test:
	cd $(AGENT_DIR) && pytest

# ── Evals ────────────────────────────────────────────────────────────────────
eval:
	cd $(AGENT_DIR) && $(PYTHON) -m evals.harness

# ── Lint / type check ────────────────────────────────────────────────────────
lint:
	cd $(AGENT_DIR) && ruff check . && ruff format --check .

type-check:
	cd $(AGENT_DIR) && mypy agent/ api/
	cd $(WEB_DIR)   && npm run type-check

# ── Seed ────────────────────────────────────────────────────────────────────
seed:
	cd $(AGENT_DIR) && $(PYTHON) scripts/seed.py

# ── Golden cases ─────────────────────────────────────────────────────────────
golden:
	cd $(AGENT_DIR) && $(PYTHON) evals/golden_dataset/generate.py

# ── Clean ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(AGENT_DIR)/.pytest_cache $(AGENT_DIR)/htmlcov $(AGENT_DIR)/.coverage
	rm -rf $(WEB_DIR)/.next $(WEB_DIR)/node_modules
