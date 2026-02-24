# Base image with uv pre-installed (Python 3.13 on Alpine)
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS builder

# Improve runtime performance and container compatibility
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Set working directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project into the image
COPY . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Expose port
EXPOSE 8080

# Default command to run the FastAPI app using the installed package
CMD ["uv", "run", "uvicorn", "hestia.app:app", "--host", "0.0.0.0", "--port", "8080"]
