# Base image with uv pre-installed (Python 3.12 on Alpine)
FROM ghcr.io/astral-sh/uv:python3.12-alpine

# Set working directory
WORKDIR /app

# Copy project metadata and lockfile
COPY pyproject.toml uv.lock ./

# Install dependencies (without project code)
RUN uv sync --locked

# Copy application source
COPY . .

# Install the project as a package (no-deps to avoid reinstalling dependencies)
RUN uv pip install --no-deps .

# Expose port
EXPOSE 8080

# Default command to run the FastAPI app using the installed package
CMD ["uv", "run", "uvicorn", "hestia.app:app", "--host", "0.0.0.0", "--port", "8080"]
