# ==========================================
# STAGE 1: Build the React Frontend
# ==========================================
FROM node:24-alpine AS frontend-builder

# Set working directory for frontend
WORKDIR /build/frontend

# Copy frontend dependency files and install
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend code and build
COPY frontend/ ./
RUN npm run build
# The compiled UI is now sitting in /build/frontend/dist


# ==========================================
# STAGE 2: Build and Run the Python Backend
# ==========================================
FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Improve runtime performance and container compatibility
# Added SKIP_FRONTEND_BUILD=1 to bypass hatch_build.py's npm check
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    SKIP_FRONTEND_BUILD=1  

# Set working directory
WORKDIR /app

# Install dependencies (ignoring the local project for cache optimization)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the Python project files into the image
COPY . /app

# Inject the pre-built frontend from Stage 1 into the Python package directory
COPY --from=frontend-builder /build/frontend/dist /app/src/hestia/ui

# Sync the project (installs the local package and metadata)
# Because SKIP_FRONTEND_BUILD=1 is set, hatchling safely uses the injected UI files
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Expose port
EXPOSE 8080

# Default command to run the FastAPI app using the installed package
CMD ["uv", "run", "uvicorn", "hestia.app:app", "--host", "0.0.0.0", "--port", "8080"]