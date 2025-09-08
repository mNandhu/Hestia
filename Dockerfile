# syntax=docker/dockerfile:1

# === Builder ===
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install uv
COPY . .
RUN uv pip install . && uv pip install .[dev]

# === Runtime ===
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY src ./src
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "hestia.app:app", "--host", "0.0.0.0", "--port", "8080"]
