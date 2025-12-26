FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY ../shared ./shared

# Create non-root user
RUN groupadd -r processor && useradd -r -g processor processor
RUN chown -R processor:processor /app
USER processor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; import main; print('Health check passed')" || exit 1

# Run the data processor
CMD ["python", "main.py"]