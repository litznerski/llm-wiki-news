# services/fastmcp/Dockerfile
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app

WORKDIR /app

# Install minimal system dependencies for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml /app/services/fastmcp/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary \
        "fastmcp>=0.4.0" \
        "httpx>=0.27.0" \
        "pydantic>=2.0.0" \
        "fastapi>=0.110.0" \
        "uvicorn>=0.28.0" \
        "python-dotenv>=1.0.0" \
        "langfuse>=2.0.0"

# Copy application source code into package structure
COPY . /app/services/fastmcp/

# Create and switch to non-root user
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "services.fastmcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
