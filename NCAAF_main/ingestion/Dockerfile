# Multi-stage build for Go ingestion service

# Stage 1: Build
FROM golang:1.23.3-alpine3.20 AS builder

# Install build dependencies
RUN apk add --no-cache git make ca-certificates tzdata

# Set working directory
WORKDIR /build

# Copy go mod/sum first for better caching
COPY go.mod ./
COPY go.sum* ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Tidy modules after copying source (to get all dependencies)
RUN go mod tidy

# Build binaries with trimpath and stripped symbols for smaller output
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/worker ./cmd/worker
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/manualfetch ./cmd/manualfetch

# Stage 2: Runtime
FROM alpine:3.20 AS production

# Install minimal runtime dependencies (wget for healthcheck)
RUN apk --no-cache add ca-certificates tzdata wget

# Set working directory
WORKDIR /app

# Create non-root user early and own the app directory
RUN addgroup -S appuser && adduser -S -G appuser appuser && \
    chown -R appuser:appuser /app

# Copy binaries and assets
COPY --from=builder --chown=appuser:appuser /out/worker ./bin/worker
COPY --from=builder --chown=appuser:appuser /out/manualfetch ./bin/manualfetch
COPY --from=builder --chown=appuser:appuser /build/migrations ./migrations
COPY --from=builder --chown=appuser:appuser /build/docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh

USER appuser

# Expose ports
EXPOSE 8080 9090

# Health check hits the built-in handler
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Set entrypoint for flexible command support
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command is "worker" (overridable in docker-compose)
CMD ["worker"]
