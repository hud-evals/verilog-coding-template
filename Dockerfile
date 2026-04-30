# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS setup

# Update and install core dependencies
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends \
  vim \
  openssl \
  ca-certificates \
  curl \
  wget \
  sudo \
  bash \
  net-tools \
  python3 \
  python3-pip \
  python3-dev \
  python3-wheel \
  python3-venv \
  locales \
  libpq5 \
  sqlite3 \
  psmisc \
  build-essential \
  python-is-python3 \
  unzip \
  git \
  gnupg \
  gpg \
  jq \
  make \
  gcc \
  g++ \
  iverilog \
  verilator

RUN update-ca-certificates

RUN pip install uv --break-system-packages

WORKDIR /

# Install nvm for ubuntu user
USER ubuntu
ENV HOME=/home/ubuntu

# configure git
RUN git config --global user.email "agent@example.com"
RUN git config --global user.name "mr agent"


# ========================= PROJECT SETUP =========================
# CUSTOMIZE THIS SECTION FOR YOUR PROJECT
# This example shows Node.js/TypeScript setup. Adapt for your tech stack.
# Examples: Python (pip/poetry), Java (Maven/Gradle), C++ (CMake), Rust (Cargo)
# =================================================================


ARG FOLDER_NAME=example-verilog-codebase
ENV FOLDER_NAME=${FOLDER_NAME}

# Validate FOLDER_NAME is set
RUN test -n "$FOLDER_NAME" || (echo "ERROR: FOLDER_NAME not set" && exit 1)

ENV random1=random1
RUN git clone https://github.com/hud-evals/example-verilog-codebase /home/ubuntu/${FOLDER_NAME}

# Validate project directory exists after clone
RUN test -d "/home/ubuntu/$FOLDER_NAME" || (echo "ERROR: Project directory /home/ubuntu/$FOLDER_NAME does not exist" && exit 1)

WORKDIR /home/ubuntu/${FOLDER_NAME}

# Fetch all branches so patches can be generated at runtime
RUN git fetch --all

# build the project
RUN uv sync

# Protect .git from agent access (agent runs as ubuntu/uid 1000, MCP server runs as root)
# This allows setup_task to:
# 1. Generate patches at runtime (base->test, base->golden)
# 2. Checkout the baseline branch
# The agent cannot access git history or checkout solution branches
USER root
RUN mkdir -p /home/root/patches && \
    chown -R root:root /home/ubuntu/${FOLDER_NAME}/.git && \
    chmod -R 700 /home/ubuntu/${FOLDER_NAME}/.git && \
    git config --global --add safe.directory /home/ubuntu/${FOLDER_NAME}
USER ubuntu

# Set environment variables
ENV HOME=/home/ubuntu \
    DEBIAN_FRONTEND=noninteractive

USER root

# Postgres config:
ENV POSTGRES_USER=ubuntu
ENV POSTGRES_PASSWORD=ubuntu
ENV POSTGRES_DB=ubuntu

# ================================ hud evals mcp server setup ================================================
FROM setup AS runtime

# prepare for the hud evals mcp server

# Copy source and config needed for the editable install
COPY ./pyproject.toml /mcp_server/pyproject.toml
COPY ./README.md /mcp_server/README.md
COPY ./tools /mcp_server/tools
COPY ./grading /mcp_server/grading
WORKDIR /mcp_server

ENV RUST_LOG=warn
RUN uv venv && . .venv/bin/activate && uv sync --no-install-project --extra dev && uv pip install -e .
ENV PYTHONPATH=/mcp_server/.venv/lib/python3.12/site-packages:/mcp_server
ENV PATH=/mcp_server/.venv/bin:$PATH

# Copy environment structure (on PYTHONPATH via /mcp_server)
# env.py: tools + scenario registration
# tasks.py: scenario definitions + task registry
COPY ./env.py /mcp_server/env.py
COPY ./tasks.py /mcp_server/tasks.py

RUN mkdir -p /home/ubuntu/Downloads
RUN chmod 777 /home/ubuntu/Downloads

RUN chmod 777 /root

EXPOSE 3000

ARG HINTS="none"
ENV HINTS=$HINTS

# PROBLEM_ID is set at runtime via scenario args, not at build time
# It selects which patches to use from /home/root/patches/{problem_id}/
ENV PROBLEM_ID=""
ENV PATCHES_DIR=/home/root/patches

# Validate PATCHES_DIR is set
RUN test -n "$PATCHES_DIR" || (echo "ERROR: PATCHES_DIR not set" && exit 1)

# Run the HUD MCP server
CMD ["hud", "dev", "tasks:env", "--stdio"]