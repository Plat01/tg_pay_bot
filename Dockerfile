# Build stage
FROM python:3.12-slim AS builder

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Configure UV for better network resilience
ENV UV_HTTP_TIMEOUT=120
ENV UV_RETRIES=5
ENV UV_INDEX_URL=https://pypi.org/simple/
ENV UV_EXTRA_INDEX_URL=https://pypi.org/simple/

# Copy dependency files and source code
COPY pyproject.toml README.md ./
COPY src ./src

# Install dependencies with retries and timeout
RUN uv pip install --system --no-cache .

# Production stage
FROM python:3.12-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Run migrations and start the application
ENTRYPOINT ["./docker-entrypoint.sh"]