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
COPY run_today.py /app/run_today.py
COPY validate_team_matching.py /app/validate_team_matching.py
COPY run_migrations.py /app/run_migrations.py
COPY start.sh /app/start.sh

# Expose service port
EXPOSE 8082

# Default environment (override via compose/env)
# NOTE: DATABASE_URL and REDIS_URL are constructed from secrets at runtime
# Do NOT set them here - they would override secret-based construction in run_today.py
ENV PYTHONPATH=/app

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8082"]
# Force rebuild Mon, Dec 22, 2025  8:12:43 PM
