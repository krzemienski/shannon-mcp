# Multi-stage Dockerfile for Shannon MCP Server
# Build stage with optimizations for Python dependencies

FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies using uv with frozen lockfile
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/

# Runtime stage - minimal image for production
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set up virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /build/src/ ./src/
COPY config/ ./config/

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs /app/config

# Create non-root user for security
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app

USER mcp

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose MCP server ports
EXPOSE 8080 8081

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    MCP_CONFIG_PATH=/app/config/production.yaml \
    MCP_LOG_LEVEL=INFO \
    MCP_DATA_PATH=/app/data \
    MCP_LOG_PATH=/app/logs

# Run the MCP server
CMD ["shannon-mcp"]