FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8100
CMD ["uv", "run", "--no-sync", "entur-mcp", "--http", "--host", "0.0.0.0", "--port", "8100"]
