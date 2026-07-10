# Remote MCP service for AccountingQB (mcp.accountingqb.com)
# Build from the repo root:  docker build -f remote/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the accountingqb package plus remote-only deps (PyJWT, uvicorn).
COPY mcpb/ ./mcpb/
RUN pip install ./mcpb -r ./mcpb/remote-requirements.txt

# Run as non-root; tokens are never persisted (persist_tokens=False per
# request) but QB_DATA_DIR still needs to be writable for the package's
# data-dir bootstrap.
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
ENV QB_DATA_DIR=/data
USER appuser

EXPOSE 8000
CMD ["python", "-m", "accountingqb.remote"]
