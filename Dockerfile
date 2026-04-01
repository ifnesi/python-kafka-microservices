# Multi-stage build for React + Flask
# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend package files
COPY app/frontend/package.json app/frontend/package-lock.json* ./

# Install dependencies
RUN npm install

# Copy frontend source
COPY app/frontend/ ./

# Build React app
RUN npm run build

# Stage 2: Python backend with React build
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application code (excluding frontend source, we'll copy the build only)
COPY app/*.py app/*.ini ./
COPY app/requirements.txt ./
COPY app/utils ./utils
COPY app/config ./config
COPY app/schemas ./schemas
COPY app/static ./static

# Copy React build from frontend-builder stage
COPY --from=frontend-builder /frontend/build ./frontend/build

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p logs pid

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["python3"]
