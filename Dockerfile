# Use a Python base image
FROM python:3.10-slim

# Install required OS packages for psycopg2 and data processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy dependency list first (leverages Docker caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Dash default port (your app uses 8055)
EXPOSE 8055

# Run the Dash app
CMD ["python", "OutboundManual.py"]