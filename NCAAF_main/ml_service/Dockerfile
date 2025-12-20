# Multi-stage build for Python ML service

# Stage 1: Base runtime image
FROM python:3.12.7-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory
WORKDIR /app

# Stage 2: Build dependencies
FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies into a separate directory for clean copy
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# Stage 3: Production runtime
FROM base AS production

# Install minimal runtime libs (libpq for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY main.py /app/
COPY src /app/src
COPY scripts /app/scripts

# Create models directory (models will be mounted via volume in production)
RUN mkdir -p /app/models

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
