# Ratings Sync Service (Go)
# Multi-stage build for small runtime image
FROM golang:1.22-alpine AS builder
WORKDIR /src

# Install CA certificates (used in final image too)
RUN apk add --no-cache ca-certificates && update-ca-certificates

# Copy module files first for caching
COPY go.mod go.sum* /src/
RUN go mod download

# Copy source
COPY . /src

# Build
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/ratings-sync ./main.go

# Runtime
FROM alpine:3.19
RUN apk add --no-cache ca-certificates && update-ca-certificates
WORKDIR /app
COPY --from=builder /out/ratings-sync /app/ratings-sync

ENV DATABASE_URL=postgres://ncaam:ncaam@postgres:5432/ncaam \
    RUN_ONCE=false

ENTRYPOINT ["/app/ratings-sync"]
