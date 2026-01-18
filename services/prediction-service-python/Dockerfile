# NCAA Prediction Service (Python) - HARDENED
# Multi-stage build to include Go/Rust binaries (reuse existing proven logic)

# Stage 1: Build Go binary (ratings-sync) - REUSE existing normalization
FROM golang:1.22-alpine AS go-builder
WORKDIR /src
# Build context is from project root, so paths are relative to that
COPY services/ratings-sync-go/go.mod services/ratings-sync-go/go.sum* ./
RUN go mod download
COPY services/ratings-sync-go/ ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s" \
    -a -installsuffix cgo \
    -o /out/ratings-sync ./main.go

# Stage 2: Build Rust binary (odds-ingestion) - REUSE existing first half/full game logic
FROM rust:latest AS rust-builder
WORKDIR /app
RUN cargo new --bin odds-ingestion
WORKDIR /app/odds-ingestion
COPY services/odds-ingestion-rust/Cargo.toml ./Cargo.toml
RUN cargo fetch
COPY services/odds-ingestion-rust/src ./src
RUN cargo build --release

# Stage 3: Python runtime with binaries
FROM python:3.12-slim

ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.revision=$GIT_SHA \
    org.opencontainers.image.created=$BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GIT_SHA=$GIT_SHA \
    BUILD_DATE=$BUILD_DATE

# Create non-root user FIRST
RUN groupadd -r ncaam && useradd -r -g ncaam -u 1001 ncaam

# Install system dependencies as root, then clean up to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* /root/.cache

WORKDIR /app

# Install Python dependencies
COPY --chown=ncaam:ncaam services/prediction-service-python/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && rm -rf /root/.cache/pip

# Create bin directory and copy binaries
RUN mkdir -p /app/bin && chown ncaam:ncaam /app/bin

# Create output directory for HTML reports and CSV files
RUN mkdir -p /app/output && chown ncaam:ncaam /app/output

# Copy Go binary (from go-builder stage) - REUSE existing normalization logic
COPY --from=go-builder --chown=ncaam:ncaam /out/ratings-sync /app/bin/ratings-sync
RUN chmod +x /app/bin/ratings-sync

# Copy Rust binary (from rust-builder stage) - REUSE existing first half/full game logic
COPY --from=rust-builder --chown=ncaam:ncaam /app/odds-ingestion/target/release/odds-ingestion /app/bin/odds-ingestion
RUN chmod +x /app/bin/odds-ingestion

# Copy repo-level metadata (version) for runtime access
COPY --chown=ncaam:ncaam VERSION /app/VERSION

# Copy application code with proper ownership
COPY --chown=ncaam:ncaam services/prediction-service-python/app /app/app
COPY --chown=ncaam:ncaam services/prediction-service-python/run_today.py /app/run_today.py
COPY --chown=ncaam:ncaam services/prediction-service-python/validate_team_matching.py /app/validate_team_matching.py
COPY --chown=ncaam:ncaam services/prediction-service-python/run_migrations.py /app/run_migrations.py
COPY --chown=ncaam:ncaam services/prediction-service-python/start.sh /app/start.sh

# Optional backend support: lightweight JSON models
COPY --chown=ncaam:ncaam ncaam /app/ncaam
COPY --chown=ncaam:ncaam models/linear /app/models/linear
# Bake DB migrations and seed/verification scripts into the image so the
# entire team-matching pipeline is self-contained inside the container.
COPY --chown=ncaam:ncaam database/migrations /app/migrations
COPY --chown=ncaam:ncaam database/seeds /app/database/seeds

# Build-time smoke check: validate imports and basic wiring.
RUN python -c "from app.main import app; assert app is not None; print('smoke_import_ok')"
# Fix line endings (CRLF -> LF) and make executable
RUN sed -i 's/\r$//' /app/start.sh 2>/dev/null || true && chmod +x /app/start.sh
RUN chmod +x /app/run_migrations.py

# Switch to non-root user
USER ncaam

# Expose service port
EXPOSE 8082

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/health').read()"

# Run all services via start script
# Use bash explicitly to avoid shebang path issues
CMD ["/usr/bin/bash", "/app/start.sh"]
