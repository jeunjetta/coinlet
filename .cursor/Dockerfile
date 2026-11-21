FROM ubuntu:24.04

ARG NODE_VERSION=22.23.4
ARG PYTHON_VERSION=3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    xz-utils \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for chrome-devtools-mcp and TypeScript projects)
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    | tar -xJ -C /usr/local --strip-components=1 --no-same-owner \
    && corepack enable

# Install uv for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv

# Install pip-audit and safety for Python security scanning
RUN pip3 install --break-system-packages pip-audit safety

USER ubuntu
WORKDIR /home/ubuntu
