# Mock Ethereum WebSocket server (Story 0.5) — replays tick-data fixtures so
# Epic 1 tracks and CI can develop against a real eth_subscribe protocol
# without an Alchemy/Infura key.
FROM python:3.11-slim

WORKDIR /app

# Install runtime deps first (better layer caching): only pyproject changes
# bust this layer, not every source edit.
COPY pyproject.toml README.md ./
COPY core ./core
COPY tools ./tools
RUN pip install --no-cache-dir .

# Fixtures are the replay data source (Story 0.4). They are NOT part of the
# installed wheel (they are data, not a Python package), so this COPY is the
# required delivery mechanism — placed at /app where replay.py resolves them via
# REPO_ROOT (or QR_FIXTURES_DIR). Copied last so editing them does not rebuild
# the dependency layer.
COPY fixtures ./fixtures

EXPOSE 8546 8547

# Bind 0.0.0.0 so the WS/health ports are reachable from outside the container.
CMD ["python", "-m", "tools.mock_wss", "--scenario", "luna", "--speed", "100x", "--host", "0.0.0.0"]
