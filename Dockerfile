FROM python:3.11-slim

WORKDIR /app

# Install pip and dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Run bot
CMD ["python", "main.py"]
