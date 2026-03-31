# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS setup

# Update and install core dependencies (including working Chromium browser)
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
  novnc \
  x11vnc \
  xvfb \
  python3 \
  python3-pip \
  python3-dev \
  python3-tk \
  python3-wheel \
  python3-venv \
  xfce4 \
  locales \
  libpq5 \
  sqlite3 \
  dbus-x11 \
  xfce4-terminal \
  xfonts-base \
  xdotool \
  psmisc \
  scrot \
  imagemagick \
  pm-utils \
  build-essential \
  python-is-python3 \
  unzip \
  git \
  xauth \
  ffmpeg \
  nginx \
  gnupg \
  gpg \ 
  jq \
  build-essential \
  python3 \
  make \
  gcc \
  g++ \
  libcairo2-dev \
  libjpeg-turbo8-dev \
  libpng-dev \
  libwebp-dev \
  libtiff-dev \
  libgif-dev \
  libvips-dev \
  libgstreamer1.0-0 \
  libgtk-4-1 \
  libgraphene-1.0-0 \
  libwoff1 \
  libevent-2.1-7 \
  libgstreamer-plugins-base1.0-0 \
  libgstreamer-plugins-good1.0-0 \
  libgstreamer-gl1.0-0 \
  libgstreamer-plugins-bad1.0-0 \
  libavif16 \
  libenchant-2-2 \
  libsecret-1-0 \
  libhyphen0 \
  libmanette-0.2-0 \
  libgles2 \
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

ENV random1=random1
RUN git clone https://github.com/hud-evals/example-verilog-codebase /home/ubuntu/${FOLDER_NAME}

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
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1.0 \
    DISPLAY_WIDTH=1280 \
    DISPLAY_HEIGHT=800

EXPOSE 6080

# supress AT-SPI errors
ENV NO_AT_BRIDGE=1
USER root

# Setup and start dinit
COPY dinit.d/ /etc/dinit.d/
RUN mkdir -p /var/log/dinit && chmod 755 /var/log/dinit

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
COPY ./src /mcp_server/src
WORKDIR /mcp_server

ENV RUST_LOG=warn
RUN uv venv && . .venv/bin/activate && uv sync --no-install-project --extra dev && uv pip install -e .
ENV PYTHONPATH=/mcp_server/.venv/lib/python3.12/site-packages:/mcp_server
ENV PATH=/mcp_server/.venv/bin:$PATH

# Copy environment structure (on PYTHONPATH via /mcp_server)
# env.py: tools + scenario registration
# tasks/: scenario definitions
# grading/: grading module
COPY ./env.py /mcp_server/env.py
COPY ./grading /mcp_server/grading
COPY ./tasks /mcp_server/tasks

ENV WIDTH=1280
ENV HEIGHT=800
ENV DISPLAY_NUM=1
RUN mkdir -p /home/ubuntu/screenshots
RUN chmod 777 /home/ubuntu/screenshots
ENV SCREENSHOT_DIR=/home/ubuntu/screenshots
RUN mkdir -p /home/ubuntu/Downloads
RUN chmod 777 /home/ubuntu/Downloads

RUN chmod 777 /root

EXPOSE 6080 3000

ARG HINTS="none"
ENV HINTS=$HINTS

# PROBLEM_ID is set at runtime via scenario args, not at build time
# It selects which patches to use from /home/root/patches/{problem_id}/
ENV PROBLEM_ID=""
ENV PATCHES_DIR=/home/root/patches

# Run the HUD MCP server
CMD ["hud", "dev", "env:env", "--stdio"]