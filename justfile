# Hestia task menu. `just` lists recipes.

backend := "packages/backend"

default:
    @just --list

# Backend with auto-reload on :8080 (reads ./hestia.yml)
dev:
    uv run --project {{backend}} uvicorn --factory hestia.main:app_factory --reload --reload-dir {{backend}}/src --host 0.0.0.0 --port 8080

# Run the gateway as in production
serve:
    uv run --project {{backend}} hestia serve

# Validate hestia.yml
check:
    uv run --project {{backend}} hestia check

# Backend tests; extra args go to pytest
test *args:
    cd {{backend}} && uv run pytest {{args}}

# Lint + format check (what CI runs)
lint:
    cd {{backend}} && uv run ruff check . && uv run ruff format --check .

# Auto-fix lint and format
fmt:
    cd {{backend}} && uv run ruff check --fix . && uv run ruff format .
