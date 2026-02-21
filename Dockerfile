FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg gcc libxml2-dev libxslt-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY src/ ./src/
COPY main.py .

# Expose output and assets as volumes
VOLUME ["/app/output", "/app/assets/commercials"]

# Start point
CMD ["python", "main.py"]
