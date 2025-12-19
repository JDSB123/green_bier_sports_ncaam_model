# NCAA Prediction Service (Python) - FastAPI
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app /app/app

# Expose service port
EXPOSE 8082

# Default environment (override via compose/env)
ENV DATABASE_URL=postgresql+asyncpg://ncaam:ncaam@postgres:5432/ncaam \
    REDIS_URL=redis://redis:6379

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
