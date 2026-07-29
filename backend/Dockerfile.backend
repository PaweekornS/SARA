# Use a lightweight, official Python 3.11 image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output for real-time logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (build tools, PostgreSQL client libraries, and ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (takes advantage of Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Default command (will be overridden in docker-compose for workers & MCP server)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]