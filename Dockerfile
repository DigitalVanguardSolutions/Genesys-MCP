# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.12

# TODO(release): pin by digest before v1.0 — `python:3.12-slim@sha256:<digest>`
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install .


# TODO(release): pin by digest before v1.0 — `python:3.12-slim@sha256:<digest>`
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    MCP_TRANSPORT=stdio \
    MCP_HOST=127.0.0.1 \
    MCP_PORT=8000

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 genesys \
    && useradd --system --uid 1001 --gid genesys --home /home/genesys --create-home genesys

COPY --from=builder /opt/venv /opt/venv

USER genesys
WORKDIR /home/genesys

EXPOSE 8000

ENTRYPOINT ["genesys-mcp"]
CMD []
