# Multi-stage builds produce smaller images by separating the
# "build" environment (has pip, compilers, build tools) from the
# "runtime" environment (only has what the app needs to run).
#
# This image is used for BOTH the FastAPI server and the Celery worker.
# Same code, different startup commands. Docker Compose overrides
# the CMD for each service.
#
# STAGE 1 (builder): Install all Python dependencies
# STAGE 2 (runtime): Copy only the installed packages + source code
# ============================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

# Set working directory inside the container
WORKDIR /app

# Install system dependencies needed for building Python packages.
# - gcc: C compiler needed by some pip packages (like psycopg2)
# - libpq-dev: PostgreSQL client library headers (needed by psycopg2)
# These are only needed during build, not runtime — that's why
# we install them in the builder stage and not the runtime stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (before source code).
# Docker caches each layer. If requirements.txt hasn't changed,
# Docker reuses the cached pip install layer — even if your source
# code changed. This makes rebuilds fast (seconds instead of minutes).
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy source code
COPY . .

# --- Stage 2: Runtime ---
FROM python:3.12-slim

WORKDIR /app

# Install ONLY the runtime system dependencies.
# libpq5 is the PostgreSQL client library (runtime version, no headers).
# We don't need gcc or libpq-dev anymore — those were only for building.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage.
# --from=builder means "copy from the builder stage, not the local filesystem"
# /install is where we told pip to install (--prefix=/install)
COPY --from=builder /install /usr/local

# Copy source code from builder stage
COPY --from=builder /app /app

# Expose the port FastAPI runs on
EXPOSE 8000

# Default command: run the FastAPI server.
# The Celery worker overrides this in docker-compose.yml.
#
# --host 0.0.0.0: Listen on all network interfaces, not just localhost.
# Inside a container, localhost means "this container only."
# 0.0.0.0 means "accept connections from anywhere" — which is needed
# because other containers (frontend) connect via Docker's network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]