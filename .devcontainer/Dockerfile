# Devcontainer image that pre-installs base Python dependencies for Codespaces
FROM mcr.microsoft.com/devcontainers/python:3.12

ARG INSTALL_HEAVY=false

ENV PIP_NO_WARN_SCRIPT_LOCATION=0

USER root

# Install system packages needed for building some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    apt-transport-https \
    ca-certificates \
    lsb-release \
    gnupg \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Copy requirements and install base dependencies into image
COPY services/prediction-service-python/requirements-base.txt /tmp/requirements-base.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements-base.txt && \
    rm -f /tmp/requirements-base.txt

# Optionally install heavy requirements if requested at build time
COPY services/prediction-service-python/requirements-heavy.txt /tmp/requirements-heavy.txt
RUN if [ "${INSTALL_HEAVY}" = "true" ]; then \
      pip install --no-cache-dir -r /tmp/requirements-heavy.txt ; \
    fi && rm -f /tmp/requirements-heavy.txt || true

# Create marker file so post-create script can skip base installs
RUN touch /usr/local/.image_built_base

USER codespace

WORKDIR /workspaces/green_bier_sports_ncaam_model
