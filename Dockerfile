# Use a lightweight official Python image
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies if needed (none are strictly required for our libraries, but curl is good to have)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Set environment variable defaults
ENV HOST=0.0.0.0
ENV PORT=8000

# Default command starts the web dashboard server
CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
