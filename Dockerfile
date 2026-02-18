# Use Python 3.11 slim image for smaller size and better performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for potential native packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create ml_models directory if it doesn't exist
RUN mkdir -p ml_models/training_data

# Expose port (Railway will provide $PORT)
EXPOSE 8000

# Default command (Railway will override this)
CMD ["python", "main.py"]
