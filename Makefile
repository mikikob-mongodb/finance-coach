.PHONY: setup run reset seed indexes test lint format clean

# Create indexes + seed data
setup: indexes seed

# Run the Streamlit app
run:
	streamlit run app.py

# Reset to pre-loaded state (clear agent-written memories)
reset:
	python scripts/reset_demo.py

# Seed transactions + snapshot only
seed:
	python scripts/seed_data.py

# Create vector, text, TTL indexes
indexes:
	python scripts/setup_indexes.py

# Run tests
test:
	pytest

# Lint with ruff
lint:
	ruff check .
	ruff format --check .

# Format with ruff
format:
	ruff format .
	ruff check --fix .

# Remove .pyc, __pycache__, .pytest_cache
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
