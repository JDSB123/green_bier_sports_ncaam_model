# Odds Ingestion Service (Rust) - Hardened
FROM rust:latest AS builder
WORKDIR /app

# Create a new empty project to leverage dependency caching
RUN cargo new --bin odds-ingestion
WORKDIR /app/odds-ingestion

# Copy manifest and fetch deps
COPY Cargo.toml ./Cargo.toml
RUN cargo fetch

# Copy source
COPY src ./src

# Build release with optimizations
RUN cargo build --release

# Runtime image - hardened
FROM debian:bookworm-slim

# Create non-root user
RUN groupadd -r ncaam && useradd -r -g ncaam -u 1001 ncaam && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy binary with proper ownership
COPY --from=builder --chown=ncaam:ncaam /app/odds-ingestion/target/release/odds-ingestion /app/odds-ingestion

# Switch to non-root user
USER ncaam

ENV RUST_LOG=info

EXPOSE 8083
ENTRYPOINT ["/app/odds-ingestion"]
