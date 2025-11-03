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
  libgles2

RUN update-ca-certificates

WORKDIR /

# Install nvm for ubuntu user
USER ubuntu
ENV HOME=/home/ubuntu

# configure git
RUN git config --global user.email "agent@example.com"
RUN git config --global user.name "mr agent"

# install elan
RUN curl https://elan.lean-lang.org/elan-init.sh -sSf > /tmp/elan-init.sh && \
    chmod +x /tmp/elan-init.sh && \
    /tmp/elan-init.sh -y && \
    rm /tmp/elan-init.sh
ENV PATH="/home/ubuntu/.elan/bin:$PATH"
RUN echo "PATH=/home/ubuntu/.elan/bin:$PATH" >> /home/ubuntu/.bash_profile

# ========================= PROJECT SETUP =========================
# CUSTOMIZE THIS SECTION FOR YOUR PROJECT
# This example shows Node.js/TypeScript setup. Adapt for your tech stack.
# Examples: Python (pip/poetry), Java (Maven/Gradle), C++ (CMake), Rust (Cargo)
# =================================================================



# 0) Clone or copy your project repository
# Replace with your repo URL and credentials if needed
# ENV GITHUB_TOKEN_BASE64=[YOUR_GITHUB_TOKEN_BASE64]
# ENV GITHUB_USERNAME=[YOUR_GITHUB_USERNAME]
# Example for private repo:
# RUN cd /home/ubuntu && \
#     GITHUB_TOKEN=$(echo "$GITHUB_TOKEN_BASE64" | base64 -d); \
#     git clone https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/your-org/your-repo /home/ubuntu/[PROJECT_NAME]
# Example for public repo:
RUN git clone https://github.com/hud-evals/example-lean-codebase /home/ubuntu/example-lean-codebase

WORKDIR /home/ubuntu/example-lean-codebase

# Checkout branches for testing (baseline, test, golden)
ARG TEST_BRANCH
ARG GOLDEN_BRANCH
ARG BASELINE_BRANCH
RUN git checkout $BASELINE_BRANCH && \
    git checkout $TEST_BRANCH && \
    git checkout $GOLDEN_BRANCH && \
    git checkout $BASELINE_BRANCH

# Generate patches for grading
USER root
RUN mkdir -p /home/root && \
    sudo -u ubuntu git diff $BASELINE_BRANCH $TEST_BRANCH > /home/root/test.patch && \
    sudo -u ubuntu git diff $BASELINE_BRANCH $GOLDEN_BRANCH > /home/root/golden.patch
USER ubuntu

# Overwrite git history to avoid leaking info
RUN rm -rf .git && git init && git add . && git commit -m "Initial commit"

# build the project
RUN lake exe cache get && lake build

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
RUN pip install uv --break-system-packages

# copy python files
COPY ./src /mcp_server/src
COPY ./pyproject.toml /mcp_server/pyproject.toml
COPY ./README.md /mcp_server/README.md

ENV RUST_LOG=warn
RUN cd /mcp_server && uv venv && . .venv/bin/activate && uv sync && uv pip install -e . 
ENV PYTHONPATH=/mcp_server/.venv/lib/python3.10/site-packages
ENV PATH=/mcp_server/.venv/bin:$PATH

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

ARG PROBLEM_ID
ENV PROBLEM_ID=$PROBLEM_ID

CMD ["tail", "-f", "/dev/null"]