# ==========================================
# STAGE 1: Build the React Frontend
# ==========================================
FROM node:24-alpine AS frontend-builder

# Set working directory for frontend
WORKDIR /build/frontend

# Copy frontend dependency files and install
COPY frontend/package*.json ./
RUN if [ -f package-lock.json ]; then \
            npm ci || npm ci --legacy-peer-deps; \
        else \
            npm install || npm install --legacy-peer-deps; \
        fi

# Copy the rest of the frontend code and build
COPY frontend/ ./
RUN npm run build
# The compiled UI is now sitting in /build/frontend/dist


# ==========================================
# STAGE 2: Build and Run the Python Backend
# ==========================================
FROM ghcr.io/astral-sh/uv:python3.13-alpine

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
