# services/frontend/Dockerfile
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHAINLIT_HOST=0.0.0.0 \
    CHAINLIT_PORT=8080

WORKDIR /app

# Install minimal system dependencies for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source, public assets, and config
COPY app.py valves.json chainlit.md /app/
COPY public/ /app/public/
COPY .chainlit/ /app/.chainlit/

# Create and switch to non-root user
RUN useradd -u 1000 -m appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8080", "--headless"]
