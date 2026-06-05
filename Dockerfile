# syntax=docker/dockerfile:1
# SPDX-License-Identifier: Apache-2.0

# python:3.12-slim pinned 2026-06-04
# To refresh: docker pull python:3.12-slim && docker inspect --format '{{index .RepoDigests 0}}'
ARG BASE_IMAGE=python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

# ---------- builder ----------
FROM ${BASE_IMAGE} AS builder
# build-essential needed to compile capstone from source on arm64
# (capstone 4.x has no aarch64 wheel; pyocd 0.36 requires capstone<5)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN pip install --no-cache-dir "build>=1.2"
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m build --wheel
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir dist/*.whl

# ---------- runtime ----------
FROM ${BASE_IMAGE} AS runtime

ARG DOCKER_BUILD_REVISION=dev
ARG DOCKER_BUILD_VERSION=dev
LABEL org.opencontainers.image.title="brontes-probe-mcp"
LABEL org.opencontainers.image.description="Multi-client debug-probe broker MCP server — session lifecycle, probe operations, ITM/SWO trace, lane supervision"
LABEL org.opencontainers.image.source="https://github.com/cms-pm/brontes-probe-mcp"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.vendor="cms-pm"
LABEL org.opencontainers.image.version="${DOCKER_BUILD_VERSION}"
LABEL org.opencontainers.image.revision="${DOCKER_BUILD_REVISION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libusb-1.0-0 \
        udev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ENV PROBE_BROKER_TRANSPORTS=stdio,socket \
    PROBE_BROKER_SOCKET_PATH=/run/brontes-probe-mcp/probe.sock \
    PROBE_BROKER_LOG_DIR=/run/brontes-probe-mcp/logs

VOLUME ["/run/brontes-probe-mcp"]

ENTRYPOINT ["python", "-m", "brontes_probe_mcp"]
