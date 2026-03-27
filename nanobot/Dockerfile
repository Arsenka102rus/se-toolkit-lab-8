# Multi-stage build for nanobot gateway
FROM harbor.pg.innopolis.university/docker-hub-cache/astral/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Copy dependency files from workspace root
COPY --from=workspace pyproject.toml uv.lock /app/
COPY pyproject.toml /app/nanobot/pyproject.toml

# Sync dependencies (frozen to use lockfile)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package nanobot

# Copy the nanobot project
COPY . /app/nanobot

# Copy workspace dependencies needed at runtime
COPY --from=workspace mcp /app/mcp
COPY --from=workspace nanobot-websocket-channel /app/nanobot-websocket-channel

# Install pip into the venv (uv doesn't include it by default)
RUN /app/.venv/bin/pip install --upgrade pip || /app/.venv/bin/python -m ensurepip --upgrade

# Final stage - runtime
FROM harbor.pg.innopolis.university/docker-hub-cache/python:3.14.2-slim-bookworm

# Create nonroot user
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 --create-home nonroot

# Copy built application
COPY --from=builder --chown=nonroot:nonroot /app /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Run the entrypoint
CMD ["python", "/app/nanobot/entrypoint.py"]
